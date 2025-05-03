from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from app.models.clients.client_details import Client
from app.models.clients.broker_details import Broker
from app.models.clients.distributor_details import Distributor
from app.models.accounts.single_account import SingleAccount
from app.schemas.clients.client_details import (
    ClientCreateRequest,
    BulkClientResponse,
    BulkClientResult,
)
from app.models.accounts.account_ideal_portfolio import AccountIdealPortfolio
from app.models.accounts.account_actual_portfolio import AccountActualPortfolio
from app.models.accounts.account_performance import AccountPerformance
from app.models.accounts.joint_account_mapping import JointAccountMapping
from app.logger import logger, log_function_call

class ClientService:
    @staticmethod
    @log_function_call
    async def get_all_clients(db: AsyncSession) -> List[Client]:
        """Fetch all client records with related broker and distributor data."""
        logger.info("Starting fetch of all client records")
        try:
            result = await db.execute(
                select(Client)
                .options(
                    selectinload(Client.broker),
                    selectinload(Client.distributor),
                    selectinload(Client.account)
                )
            )
            clients = result.scalars().all()
            logger.debug(f"Successfully retrieved {len(clients)} client records")
            return clients
        except Exception as e:
            logger.error(f"Database error fetching clients: {str(e)}", exc_info=True)
            raise ValueError("Failed to retrieve clients due to database error") from e

    @staticmethod
    @log_function_call
    async def bulk_create_clients(
        db: AsyncSession,
        data_list: List[ClientCreateRequest],
    ) -> BulkClientResponse:
        """Bulk create clients, each in its own transaction block for partial success."""
        logger.info(f"Starting bulk create for {len(data_list)} clients")
        total = len(data_list)
        results: List[BulkClientResult] = []
        processed_count = 0

        for idx, row in enumerate(data_list):
            row_index = idx + 1
            logger.debug(f"Processing row {row_index}")
            if not row.client_name or not row.broker_name or not row.pan_no:
                msg = "Missing mandatory field: client_name, broker_name, or pan_no."
                results.append(BulkClientResult(
                    row_index=row_index,
                    status="failed",
                    detail=msg
                ))
                logger.warning(f"Row {row_index} - {msg}")
                continue

            async with db.begin():
                try:
                    broker = await ClientService._get_broker_by_name(db, row.broker_name)
                    if not broker:
                        detail = f"Broker '{row.broker_name}' not found."
                        results.append(BulkClientResult(
                            row_index=row_index,
                            status="failed",
                            detail=detail
                        ))
                        logger.warning(f"Row {row_index} - {detail}")
                        continue

                    new_acc = SingleAccount(
                        account_name=row.client_name[:50].strip().title(),
                        account_type="single",
                        portfolio_id=1,
                        bracket_id=None,
                    )
                    db.add(new_acc)
                    await db.flush()
                    logger.debug(f"Created SingleAccount with ID: {new_acc.single_account_id}")

                    new_client = Client(
                        client_name=row.client_name.strip().title(),
                        broker_id=broker.broker_id,
                        broker_code=(row.broker_code or "").strip(),
                        broker_passwd=(row.broker_passwd or "").strip(),
                        email_id=(row.email_id or "").strip() if row.email_id else None,
                        pan_no=row.pan_no.strip(),
                        phone_no=row.phone_no,
                        country_code=row.country_code,
                        addr=(row.addr or "").strip(),
                        acc_start_date=row.acc_start_date,
                        distributor_id=None,
                        account_id=new_acc.single_account_id,
                        type=(row.type or "").strip(),
                        alias_name=(row.alias_name or "").strip(),
                        alias_phone_no=(row.alias_phone_no or "").strip(),
                        alias_addr=(row.alias_addr or "").strip(),
                        onboard_status="pending"
                    )
                    if row.distributor_name:
                        dist_id = await ClientService._get_distributor_id(db, row.distributor_name)
                        if dist_id:
                            new_client.distributor_id = dist_id
                            logger.debug(f"Assigned distributor ID: {dist_id}")
                        else:
                            logger.info(f"Distributor '{row.distributor_name}' not found for row {row_index}, ignoring.")

                    db.add(new_client)
                    await db.flush()
                    logger.info(f"Client created with ID: {new_client.client_id}")

                    results.append(BulkClientResult(
                        row_index=row_index,
                        status="success",
                        detail="Inserted successfully",
                        client_id=new_client.client_id
                    ))
                    processed_count += 1

                except Exception as exc:
                    logger.error(f"Row {row_index} create failed: {str(exc)}", exc_info=True)
                    results.append(BulkClientResult(
                        row_index=row_index,
                        status="failed",
                        detail=f"DB error: {str(exc)}"
                    ))

        logger.info(f"Bulk create completed: {processed_count}/{total} rows processed")
        return BulkClientResponse(
            total_rows=total,
            processed_rows=processed_count,
            results=results
        )

    @staticmethod
    @log_function_call
    async def bulk_update_clients(
        db: AsyncSession,
        data_list: List[ClientCreateRequest],
    ) -> BulkClientResponse:
        """Bulk update clients with partial success."""
        logger.info(f"Starting bulk update for {len(data_list)} clients")
        total = len(data_list)
        results: List[BulkClientResult] = []
        processed_count = 0

        for idx, row in enumerate(data_list):
            row_index = idx + 1
            logger.debug(f"Processing row {row_index}")
            if not row.client_id:
                detail = "No client_id provided for update."
                results.append(BulkClientResult(
                    row_index=row_index,
                    status="failed",
                    detail=detail
                ))
                logger.warning(f"Row {row_index} - {detail}")
                continue

            async with db.begin():
                try:
                    client_obj = await db.get(Client, row.client_id)
                    if not client_obj:
                        detail = f"Client '{row.client_id}' not found."
                        results.append(BulkClientResult(
                            row_index=row_index,
                            status="failed",
                            detail=detail
                        ))
                        logger.warning(f"Row {row_index} - {detail}")
                        continue

                    if row.broker_name is not None:
                        broker = await ClientService._get_broker_by_name(db, row.broker_name)
                        if not broker:
                            detail = f"Broker '{row.broker_name}' not found."
                            results.append(BulkClientResult(
                                row_index=row_index,
                                status="failed",
                                detail=detail
                            ))
                            logger.warning(f"Row {row_index} - {detail}")
                            continue
                        client_obj.broker_id = broker.broker_id
                        logger.debug(f"Updated broker_id to {broker.broker_id}")

                    if row.client_name is not None:
                        client_obj.client_name = row.client_name.strip()
                    if row.broker_code is not None:
                        client_obj.broker_code = row.broker_code.strip()
                    if row.broker_passwd is not None:
                        client_obj.broker_passwd = row.broker_passwd.strip()
                    if row.pan_no is not None:
                        client_obj.pan_no = row.pan_no.strip()
                    if row.email_id is not None:
                        client_obj.email_id = row.email_id.strip()
                    if row.country_code is not None:
                        client_obj.country_code = row.country_code
                    if row.phone_no is not None:
                        client_obj.phone_no = row.phone_no
                    if row.addr is not None:
                        client_obj.addr = row.addr.strip()
                    if row.acc_start_date is not None:
                        client_obj.acc_start_date = row.acc_start_date
                    if row.distributor_name is not None:
                        dist_id = await ClientService._get_distributor_id(db, row.distributor_name)
                        client_obj.distributor_id = dist_id
                        logger.debug(f"Updated distributor_id to {dist_id}")
                    if row.type is not None:
                        client_obj.type = row.type.strip()
                    if row.alias_name is not None:
                        client_obj.alias_name = row.alias_name.strip()
                    if row.alias_phone_no is not None:
                        client_obj.alias_phone_no = row.alias_phone_no.strip()
                    if row.alias_addr is not None:
                        client_obj.alias_addr = row.alias_addr.strip()

                    if row.client_name is not None and client_obj.account_id:
                        single_acc = await db.get(SingleAccount, client_obj.account_id)
                        if single_acc:
                            single_acc.account_name = row.client_name[:50]
                            logger.debug(f"Updated SingleAccount name to '{row.client_name[:50]}'")

                    await db.flush()
                    logger.info(f"Client {row.client_id} updated successfully")

                    results.append(BulkClientResult(
                        row_index=row_index,
                        status="success",
                        detail="Updated successfully",
                        client_id=client_obj.client_id
                    ))
                    processed_count += 1

                except Exception as exc:
                    logger.error(f"Row {row_index} update failed: {str(exc)}", exc_info=True)
                    results.append(BulkClientResult(
                        row_index=row_index,
                        status="failed",
                        detail=f"DB error: {str(exc)}"
                    ))

        logger.info(f"Bulk update completed: {processed_count}/{total} rows processed")
        return BulkClientResponse(
            total_rows=total,
            processed_rows=processed_count,
            results=results
        )

    @staticmethod
    @log_function_call
    async def bulk_delete_clients(db: AsyncSession, client_ids: List[str]) -> BulkClientResponse:
        """Bulk delete clients with partial success, also deleting associated single accounts and their dependencies."""
        logger.info(f"Starting bulk delete for {len(client_ids)} clients")
        total = len(client_ids)
        results: List[BulkClientResult] = []
        processed_count = 0

        for idx, cid in enumerate(client_ids):
            row_index = idx + 1
            logger.debug(f"Processing row {row_index} for client_id: {cid}")
            async with db.begin():
                try:
                    client_obj = await db.get(Client, cid)
                    if not client_obj:
                        detail = f"Client '{cid}' not found."
                        results.append(BulkClientResult(
                            row_index=row_index,
                            status="failed",
                            detail=detail
                        ))
                        logger.warning(f"Row {row_index} - {detail}")
                        continue

                    if client_obj.account_id:
                        joint_check = select(JointAccountMapping).where(
                            JointAccountMapping.account_id == client_obj.account_id
                        )
                        joint_result = await db.execute(joint_check)
                        joint_mappings = joint_result.scalars().all()
                        
                        if joint_mappings:
                            detail = f"Cannot delete: Account {client_obj.account_id} is part of {len(joint_mappings)} joint account(s)"
                            results.append(BulkClientResult(
                                row_index=row_index,
                                status="failed",
                                detail=detail
                            ))
                            logger.warning(f"Row {row_index} - {detail}")
                            continue

                        account_id = client_obj.account_id
                        
                        ideal_del = delete(AccountIdealPortfolio).where(
                            AccountIdealPortfolio.owner_id == account_id,
                            AccountIdealPortfolio.owner_type == "single"
                        )
                        await db.execute(ideal_del)
                        
                        actual_del = delete(AccountActualPortfolio).where(
                            AccountActualPortfolio.owner_id == account_id,
                            AccountActualPortfolio.owner_type == "single"
                        )
                        await db.execute(actual_del)
                        
                        perf_del = delete(AccountPerformance).where(
                            AccountPerformance.owner_id == account_id,
                            AccountPerformance.owner_type == "single"
                        )
                        await db.execute(perf_del)
                        
                        single_acc = await db.get(SingleAccount, client_obj.account_id)
                        if single_acc:
                            await db.delete(single_acc)
                            logger.debug(f"Deleted SingleAccount with ID: {client_obj.account_id}")

                    await db.delete(client_obj)
                    await db.flush()
                    logger.info(f"Client {cid} deleted successfully")

                    results.append(BulkClientResult(
                        row_index=row_index,
                        status="success",
                        detail="Deleted successfully",
                        client_id=cid
                    ))
                    processed_count += 1

                except Exception as exc:
                    logger.error(f"Row {row_index} delete failed: {str(exc)}", exc_info=True)
                    results.append(BulkClientResult(
                        row_index=row_index,
                        status="failed",
                        detail=f"DB error: {str(exc)}"
                    ))

        logger.info(f"Bulk delete completed: {processed_count}/{total} rows processed")
        return BulkClientResponse(
            total_rows=total,
            processed_rows=processed_count,
            results=results
        )

    @staticmethod
    async def _get_broker_by_name(db: AsyncSession, broker_name: str) -> Optional[Broker]:
        """Helper method to fetch a broker by name (case-insensitive)."""
        if not broker_name:
            logger.debug("No broker_name provided for lookup")
            return None
        stmt = select(Broker).where(Broker.broker_name.ilike(broker_name.strip()))
        result = await db.execute(stmt)
        broker = result.scalars().first()
        logger.debug(f"Broker lookup for '{broker_name}': {'found' if broker else 'not found'}")
        return broker

    @staticmethod
    async def _get_distributor_id(db: AsyncSession, dist_name: str) -> Optional[str]:
        """Helper method to fetch a distributor ID by name (case-insensitive)."""
        if not dist_name:
            logger.debug("No distributor_name provided for lookup")
            return None
        stmt = select(Distributor).where(Distributor.name.ilike(dist_name.strip()))
        result = await db.execute(stmt)
        dist_obj = result.scalars().first()
        logger.debug(f"Distributor lookup for '{dist_name}': {'found' if dist_obj else 'not found'}")
        return dist_obj.distributor_id if dist_obj else None