from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.logger import logger, log_function_call
from app.models.clients.broker_details import Broker
from app.models.clients.client_details import Client
from app.models.accounts.single_account import SingleAccount
from app.models.accounts.joint_account import JointAccount
from app.models.accounts.joint_account_mapping import JointAccountMapping
from app.models.portfolio.bracket_details import Bracket
from app.models.portfolio.portfolio_template_details import PortfolioTemplate
from app.models.accounts.account_performance import AccountPerformance
from app.schemas.accounts.account import (
    ViewAccount, BulkAccountResult, AccountUpdateRequest, BulkAccountResponse
)

class AccountService:
    @staticmethod
    @log_function_call
    async def get_all_accounts_view(db: AsyncSession) -> List[ViewAccount]:
        """Fetch and combine single and joint accounts into a unified view."""
        logger.info("Starting consolidated fetch of SingleAccount objects...")
        single_query = (
            select(SingleAccount)
            .options(
                selectinload(SingleAccount.bracket),
                selectinload(SingleAccount.portfolio_template),
                selectinload(SingleAccount.performance)
            )
        )
        single_result = await db.execute(single_query)
        single_accounts = single_result.scalars().all()
        logger.info(f"Retrieved {len(single_accounts)} single accounts.")

        logger.info("Starting consolidated fetch of JointAccount objects...")
        joint_query = (
            select(JointAccount)
            .options(
                selectinload(JointAccount.bracket),
                selectinload(JointAccount.portfolio_template),
                selectinload(JointAccount.performance)
            )
        )
        joint_result = await db.execute(joint_query)
        joint_accounts = joint_result.scalars().all()
        logger.info(f"Retrieved {len(joint_accounts)} joint accounts.")

        logger.info("Combining single and joint accounts into a unified view...")
        unified_view: List[ViewAccount] = []

        for acc in single_accounts:
            bracket_name = acc.bracket.bracket_name if acc.bracket else None
            portfolio_name = acc.portfolio_template.portfolio_name if acc.portfolio_template else None
            total_twrr = acc.performance.total_twrr if acc.performance else None
            current_yr_twrr = acc.performance.current_yr_twrr if acc.performance else None
            cagr = acc.performance.cagr if acc.performance else None

            unified_view.append(
                ViewAccount(
                    account_type="single",
                    account_id=acc.single_account_id,
                    account_name=acc.account_name,
                    bracket_name=bracket_name,
                    portfolio_name=portfolio_name,
                    pf_value=acc.pf_value,
                    cash_value=acc.cash_value,
                    total_holdings=acc.total_holdings,
                    invested_amt=acc.invested_amt,
                    total_twrr=total_twrr,
                    current_yr_twrr=current_yr_twrr,
                    cagr=cagr,
                    created_at=acc.created_at.isoformat() if acc.created_at else None,
                )
            )

        for acc in joint_accounts:
            bracket_name = acc.bracket.bracket_name if acc.bracket else None
            portfolio_name = acc.portfolio_template.portfolio_name if acc.portfolio_template else None
            total_twrr = acc.performance.total_twrr if acc.performance else None
            current_yr_twrr = acc.performance.current_yr_twrr if acc.performance else None
            cagr = acc.performance.cagr if acc.performance else None

            unified_view.append(
                ViewAccount(
                    account_type="joint",
                    account_id=acc.joint_account_id,
                    account_name=acc.joint_account_name,
                    bracket_name=bracket_name,
                    portfolio_name=portfolio_name,
                    pf_value=acc.pf_value,
                    cash_value=acc.cash_value,
                    total_holdings=acc.total_holdings,
                    invested_amt=acc.invested_amt,
                    total_twrr=total_twrr,
                    current_yr_twrr=current_yr_twrr,
                    cagr=cagr,
                    created_at=acc.created_at.isoformat() if acc.created_at else None,
                )
            )

        logger.info(f"Final unified view contains {len(unified_view)} accounts.")
        return unified_view

    @staticmethod
    async def bulk_update_accounts(db: AsyncSession, updates: List[AccountUpdateRequest]) -> BulkAccountResponse:
        """
        Bulk update single and joint accounts with partial success:
        - Single: Updates pf_value, cash_value, invested_amt, total_holdings (calculated), and performance fields.
                  Then recalculates linked joint accounts.
        - Joint: Updates only performance fields; ignores pf_value, cash_value, invested_amt.
        """
        total = len(updates)
        results: List[BulkAccountResult] = []
        processed_count = 0

        for idx, req in enumerate(updates):
            row_index = idx + 1
            async with db.begin():
                try:
                    if req.account_type == "single":
                        single_acc = await db.get(SingleAccount, req.account_id)
                        if not single_acc:
                            msg = f"Single account '{req.account_id}' not found."
                            results.append(BulkAccountResult(
                                row_index=row_index,
                                status="failed",
                                detail=msg
                            ))
                            logger.warning(f"Row {row_index} - {msg}")
                            continue

                        if req.pf_value is not None:
                            single_acc.pf_value = req.pf_value
                        if req.cash_value is not None:
                            single_acc.cash_value = req.cash_value
                        if req.invested_amt is not None:
                            single_acc.invested_amt = req.invested_amt

                        single_acc.total_holdings = (single_acc.pf_value or 0) + (single_acc.cash_value or 0)

                        if req.total_twrr is not None or req.current_yr_twrr is not None or req.cagr is not None:
                            perf = single_acc.performance
                            if not perf:
                                perf = await AccountService._create_performance(db, req.account_id, "single")
                                single_acc.performance = perf

                            if req.total_twrr is not None:
                                perf.total_twrr = req.total_twrr
                            if req.current_yr_twrr is not None:
                                perf.current_yr_twrr = req.current_yr_twrr
                            if req.cagr is not None:
                                perf.cagr = req.cagr

                        await db.flush()
                        await AccountService._recalc_all_linked_joints(db, single_acc.single_account_id)

                        results.append(BulkAccountResult(
                            row_index=row_index,
                            status="success",
                            detail="Updated single account successfully",
                            account_id=req.account_id
                        ))
                        processed_count += 1

                    elif req.account_type == "joint":
                        joint_acc = await db.get(JointAccount, req.account_id)
                        if not joint_acc:
                            msg = f"Joint account '{req.account_id}' not found."
                            results.append(BulkAccountResult(
                                row_index=row_index,
                                status="failed",
                                detail=msg
                            ))
                            logger.warning(f"Row {row_index} - {msg}")
                            continue

                        if req.total_twrr is not None or req.current_yr_twrr is not None or req.cagr is not None:
                            perf = joint_acc.performance
                            if not perf:
                                perf = await AccountService._create_performance(db, req.account_id, "joint")
                                joint_acc.performance = perf

                            if req.total_twrr is not None:
                                perf.total_twrr = req.total_twrr
                            if req.current_yr_twrr is not None:
                                perf.current_yr_twrr = req.current_yr_twrr
                            if req.cagr is not None:
                                perf.cagr = req.cagr

                        await db.flush()

                        results.append(BulkAccountResult(
                            row_index=row_index,
                            status="success",
                            detail="Updated joint account successfully",
                            account_id=req.account_id
                        ))
                        processed_count += 1

                    else:
                        msg = f"Invalid account_type '{req.account_type}'"
                        results.append(BulkAccountResult(
                            row_index=row_index,
                            status="failed",
                            detail=msg
                        ))
                        logger.warning(f"Row {row_index} - {msg}")

                except Exception as exc:
                    logger.error(f"Row {row_index} update failed: {exc}", exc_info=True)
                    results.append(BulkAccountResult(
                        row_index=row_index,
                        status="failed",
                        detail=str(exc)
                    ))

        return BulkAccountResponse(
            total_rows=total,
            processed_rows=processed_count,
            results=results
        )

    @staticmethod
    async def _recalc_all_linked_joints(db: AsyncSession, single_id: str):
        """Recalculate joint account values based on linked single accounts."""
        stmt_joints = select(JointAccountMapping.joint_account_id).where(
            JointAccountMapping.account_id == single_id
        )
        res_joints = await db.execute(stmt_joints)
        joint_ids = [r[0] for r in res_joints.fetchall()]

        for j_id in joint_ids:
            sum_stmt = (
                select(
                    func.coalesce(func.sum(SingleAccount.pf_value), 0),
                    func.coalesce(func.sum(SingleAccount.cash_value), 0),
                    func.coalesce(func.sum(SingleAccount.invested_amt), 0),
                )
                .join(JointAccountMapping, SingleAccount.single_account_id == JointAccountMapping.account_id)
                .where(JointAccountMapping.joint_account_id == j_id)
            )
            sum_res = await db.execute(sum_stmt)
            pf_sum, cash_sum, invest_sum = sum_res.fetchone()
            total_sum = pf_sum + cash_sum

            joint_acc = await db.get(JointAccount, j_id)
            if joint_acc:
                joint_acc.pf_value = pf_sum
                joint_acc.cash_value = cash_sum
                joint_acc.invested_amt = invest_sum
                joint_acc.total_holdings = total_sum
                await db.flush()

    @staticmethod
    async def _create_performance(db: AsyncSession, owner_id: str, owner_type: str) -> AccountPerformance:
        """Create a new AccountPerformance record if none exists."""
        perf_id = f"PERF_{owner_id}"
        new_perf = AccountPerformance(
            performance_id=perf_id,
            owner_id=owner_id,
            owner_type=owner_type,
            total_twrr=0,
            current_yr_twrr=0,
            cagr=0
        )
        db.add(new_perf)
        await db.flush()
        return new_perf
    
    @staticmethod
    @log_function_call
    async def get_single_accounts_with_broker_info(db: AsyncSession):
        """
        Retrieve single accounts with their associated broker codes and names.

        This function joins SingleAccount, Client, and Broker tables to fetch account_id,
        broker_code, and broker_name for accounts with a non-null broker_code.

        Args:
            db (AsyncSession): The database session for executing the query.

        Returns:
            list[dict]: A list of dictionaries containing 'account_id', 'broker_code', and 'broker_name'.
        """
        query = (
            select(
                SingleAccount.single_account_id.label("account_id"),
                Client.broker_code,
                Broker.broker_name,
                Client.acc_start_date
            )
            .join(Client, SingleAccount.single_account_id == Client.account_id)
            .join(Broker, Client.broker_id == Broker.broker_id)
            .where(Client.broker_code.isnot(None))
        )

        result = await db.execute(query)
        rows = result.all()

        return [
            {
                "account_id": row.account_id,
                "broker_code": row.broker_code,
                "broker_name": row.broker_name,
                "acc_start_date": row.acc_start_date 
            }
            for row in rows
        ]