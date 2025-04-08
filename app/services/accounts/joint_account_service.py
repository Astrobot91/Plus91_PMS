from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.clients.broker_details import Broker
from app.models.clients.client_details import Client
from app.models.accounts.joint_account import JointAccount
from app.models.accounts.single_account import SingleAccount
from app.models.accounts.joint_account_mapping import JointAccountMapping
from app.schemas.accounts.joint_account import (
    JointAccountCreateRequest, JointAccountResponse, JointAccountUpdateRequest
)
from app.logger import logger, log_function_call
from typing import List, Dict


class JointAccountService:
    @staticmethod
    @log_function_call
    async def create_joint_account(db: AsyncSession, payload: JointAccountCreateRequest) -> Optional[JointAccountResponse]:
        """Create a new joint account and map it to single accounts."""
        try:
            new_joint_account = JointAccount(
                joint_account_name=payload.joint_account_name,
                portfolio_id=1  # Default portfolio_id; adjust as needed
            )
            db.add(new_joint_account)
            await db.flush()

            for acc_id in payload.single_account_ids:
                query_single = select(SingleAccount).where(SingleAccount.single_account_id == acc_id)
                single_result = await db.execute(query_single)
                single_obj = single_result.scalar_one_or_none()

                if not single_obj:
                    logger.warning(f"SingleAccount '{acc_id}' not found. Skipping mapping.")
                    continue

                mapping_query = select(JointAccountMapping).where(JointAccountMapping.account_id == single_obj.single_account_id)
                existing_mapping_result = await db.execute(mapping_query)
                existing_mapping = existing_mapping_result.scalar_one_or_none()

                if existing_mapping:
                    logger.error(
                        f"SingleAccount '{acc_id}' is already mapped to a different JointAccount "
                        f"('{existing_mapping.joint_account_id}'). Aborting creation."
                    )
                    raise ValueError(f"SingleAccount '{acc_id}' already belongs to another JointAccount.")

                mapping = JointAccountMapping(
                    joint_account_id=new_joint_account.joint_account_id,
                    account_id=single_obj.single_account_id
                )
                db.add(mapping)

            await db.commit()
            return JointAccountResponse(
                status="success",
                joint_account_id=new_joint_account.joint_account_id,
                joint_account_name=new_joint_account.joint_account_name,
                linked_single_accounts=payload.single_account_ids
            )
        except Exception as e:
            logger.error(f"Error in create_joint_account: {e}", exc_info=True)
            await db.rollback()
            return None

    @staticmethod
    @log_function_call
    async def update_joint_account(
        db: AsyncSession,
        joint_account_id: str,
        payload: JointAccountUpdateRequest
    ) -> Optional[JointAccountResponse]:
        """Update an existing joint account's name and/or linked single accounts."""
        try:
            query_joint = select(JointAccount).where(JointAccount.joint_account_id == joint_account_id)
            result_joint = await db.execute(query_joint)
            existing_joint: JointAccount = result_joint.scalar_one_or_none()

            if not existing_joint:
                logger.warning(f"JointAccount '{joint_account_id}' not found.")
                return None

            if payload.joint_account_name is not None:
                existing_joint.joint_account_name = payload.joint_account_name.strip()

            if payload.single_account_ids is not None:
                del_stmt = delete(JointAccountMapping).where(JointAccountMapping.joint_account_id == joint_account_id)
                await db.execute(del_stmt)

                for acc_id in payload.single_account_ids:
                    query_single = select(SingleAccount).where(SingleAccount.single_account_id == acc_id)
                    single_result = await db.execute(query_single)
                    single_obj = single_result.scalar_one_or_none()

                    if not single_obj:
                        logger.warning(f"SingleAccount '{acc_id}' not found. Skipping mapping.")
                        continue

                    mapping_query = select(JointAccountMapping).where(JointAccountMapping.account_id == single_obj.single_account_id)
                    existing_mapping_result = await db.execute(mapping_query)
                    existing_mapping = existing_mapping_result.scalar_one_or_none()

                    if existing_mapping and existing_mapping.joint_account_id != joint_account_id:
                        logger.error(
                            f"SingleAccount '{acc_id}' is already mapped to another JointAccount "
                            f"('{existing_mapping.joint_account_id}'). Aborting update."
                        )
                        raise ValueError(f"SingleAccount '{acc_id}' belongs to another JointAccount.")

                    new_map = JointAccountMapping(
                        joint_account_id=joint_account_id,
                        account_id=acc_id
                    )
                    db.add(new_map)

            await db.commit()
            refresh_query = select(JointAccountMapping.account_id).where(JointAccountMapping.joint_account_id == joint_account_id)
            refresh_result = await db.execute(refresh_query)
            mapped_ids = [row[0] for row in refresh_result.all()]

            return JointAccountResponse(
                status="success",
                joint_account_id=existing_joint.joint_account_id,
                joint_account_name=existing_joint.joint_account_name,
                linked_single_accounts=mapped_ids
            )
        except Exception as e:
            logger.error(f"Error in update_joint_account: {e}", exc_info=True)
            await db.rollback()
            return None

    @staticmethod
    @log_function_call
    async def delete_joint_account(db: AsyncSession, joint_account_id: str) -> Optional[JointAccountResponse]:
        """Delete the specified joint account and its mappings."""
        try:
            query_joint = select(JointAccount).where(JointAccount.joint_account_id == joint_account_id)
            result_joint = await db.execute(query_joint)
            existing_joint = result_joint.scalar_one_or_none()

            if not existing_joint:
                logger.warning(f"JointAccount '{joint_account_id}' not found.")
                return None

            joint_name = existing_joint.joint_account_name
            await db.delete(existing_joint)
            await db.commit()
            return JointAccountResponse(
                status="success",
                joint_account_id=joint_account_id,
                joint_account_name=joint_name,
                linked_single_accounts=[]
            )
        except Exception as e:
            logger.error(f"Error in delete_joint_account: {e}", exc_info=True)
            await db.rollback()
            return None
        
    @staticmethod
    @log_function_call
    async def get_joint_accounts_with_single_accounts(db: AsyncSession) -> List[Dict]:
        """
        Retrieve all joint accounts with their associated single accounts and start dates.

        Args:
            db (AsyncSession): The database session.

        Returns:
            List[Dict]: List of dictionaries containing joint account details and their single accounts.
        """
        try:
            query = (
                select(
                    JointAccount.joint_account_id,
                    SingleAccount.single_account_id.label("account_id"),
                    Client.acc_start_date,
                    Client.broker_code,
                    Broker.broker_name
                )
                .select_from(JointAccount)
                .outerjoin(JointAccountMapping, JointAccount.joint_account_id == JointAccountMapping.joint_account_id)
                .outerjoin(SingleAccount, JointAccountMapping.account_id == SingleAccount.single_account_id)
                .outerjoin(Client, SingleAccount.single_account_id == Client.account_id)
                .outerjoin(Broker, Client.broker_id == Broker.broker_id)
            )
            result = await db.execute(query)
            rows = result.all()

            joint_accounts_dict = {}
            for row in rows:
                joint_id = row.joint_account_id
                if joint_id not in joint_accounts_dict:
                    joint_accounts_dict[joint_id] = {
                        "joint_account_id": joint_id,
                        "single_accounts": []
                    }
                if row.account_id:
                    joint_accounts_dict[joint_id]["single_accounts"].append({
                        "account_id": row.account_id,
                        "acc_start_date": row.acc_start_date,
                        "broker_code": row.broker_code,
                        "broker_name": row.broker_name,
                    })

            joint_accounts = list(joint_accounts_dict.values())
            logger.info(f"Fetched {len(joint_accounts)} joint accounts with single account mappings.")
            return joint_accounts
        except Exception as e:
            logger.error(f"Error fetching joint accounts with single accounts: {e}")
            return []
        
    @staticmethod
    @log_function_call
    async def get_linked_single_accounts(db: AsyncSession, joint_account_id: str) -> list:
        """Fetch details of single accounts linked to a joint account."""
        query = (
            select(
                SingleAccount.single_account_id.label("account_id"),
                Client.acc_start_date,
                Client.broker_code,
                Broker.broker_name
            )
            .join(JointAccountMapping, JointAccountMapping.account_id == SingleAccount.single_account_id)
            .join(Client, Client.account_id == SingleAccount.single_account_id)
            .join(Broker, Broker.broker_id == Client.broker_id)
            .where(JointAccountMapping.joint_account_id == joint_account_id)
        )
        result = await db.execute(query)
        rows = result.all()
        return [
            {
                'account_id': row.account_id,
                'acc_start_date': row.acc_start_date,
                'broker_code': row.broker_code,
                'broker_name': row.broker_name,
            }
            for row in rows
        ]