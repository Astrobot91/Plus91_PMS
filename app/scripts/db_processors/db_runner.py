import sys
import time
import asyncio
import logging
from sqlalchemy.orm import selectinload
from app.database import AsyncSessionLocal
from app.services.accounts.account_service import AccountService
from app.services.accounts.joint_account_service import JointAccountService
from app.models.accounts.single_account import SingleAccount
from app.models.accounts.joint_account import JointAccount
from app.models.accounts.account_performance import AccountPerformance
from app.scripts.data_fetchers.data_transformer import KeynoteDataTransformer, ZerodhaDataTransformer
from app.scripts.data_fetchers.portfolio_data import KeynoteDataProcessor, ZerodhaDataFetcher
from app.scripts.db_processors.cashflow_processor import CashflowProcessor
from app.scripts.db_processors.actual_portfolio_processor import ActualPortfolioProcessor
from app.scripts.db_processors.cashflow_progression_processor import CashflowProgressionProcessor
from app.scripts.db_processors.ltp_processor import LtpProcessor
from app.logger import logger

keynote_portfolio = KeynoteDataProcessor()
zerodha_portfolio = ZerodhaDataFetcher()

async def runner():
    list_of_accounts = []
    """Main function to process accounts and update all required fields."""
    try:
        keynote_portfolio.process_all_bulk_holdings_to_s3()

        async with AsyncSessionLocal() as db:
            accounts_data = await AccountService.get_single_accounts_with_broker_info(db)
            if not accounts_data:
                logger.warning("No single accounts found.")
                return

            joint_accounts = await JointAccountService.get_joint_accounts_with_single_accounts(db)
            if not joint_accounts:
                logger.warning("No joint accounts found.")
            joint_accounts = []
            cashflow_processor = CashflowProcessor(db, KeynoteDataTransformer(), ZerodhaDataTransformer())
            portfolio_processor = ActualPortfolioProcessor(db, KeynoteDataTransformer(), ZerodhaDataTransformer())
            progression_processor = CashflowProgressionProcessor(db, cashflow_processor)

            await cashflow_processor.initialize(accounts_data, joint_accounts)
            await portfolio_processor.initialize(accounts_data, joint_accounts)

            for acc in accounts_data:
                acc['account_type'] = 'single'
                invested_amt = await cashflow_processor.calculate_invested_amt(acc['account_id'], 'single')
                pf_value = await portfolio_processor.calculate_pf_value(acc['account_id'], 'single')
                portfolio_values, month_ends = await progression_processor.get_portfolio_values(acc['account_id'], 'single')
                cash_value = await cashflow_processor.calculate_cash_value(acc, month_ends)
                total_holdings = pf_value + cash_value

                month_ends_dict = {}
                month_ends_dict[acc['account_id']] = month_ends
                
                if month_ends:
                    df_single = await progression_processor.get_cashflow_progression_df(acc, month_ends_dict)

                    if not df_single.empty:
                        await progression_processor.update_cashflow_progression_table(acc, df_single)
                        logger.info(f"Updated cashflow progression for single account {acc['account_id']}")

                        time_periods_df, total_twrr, current_yr_twrr, cagr = progression_processor.get_time_periods_df(df_single)
                        await progression_processor.update_time_periods_table(acc, time_periods_df)
                        account_model = await db.get(
                            SingleAccount,
                            acc['account_id'],
                            options=[selectinload(SingleAccount.performance)]
                            )
                        if account_model:
                            account_model.invested_amt = invested_amt
                            account_model.pf_value = pf_value
                            account_model.cash_value = cash_value
                            account_model.total_holdings = total_holdings
                            if account_model.performance:
                                account_model.performance.total_twrr = total_twrr
                                account_model.performance.current_yr_twrr = current_yr_twrr
                                account_model.performance.cagr = cagr
                            else:
                                new_perf = AccountPerformance(
                                    performance_id=f"PERF_{acc['account_id']}",
                                    owner_id=acc['account_id'],
                                    owner_type='single',
                                    total_twrr=total_twrr,
                                    current_yr_twrr=current_yr_twrr,
                                    cagr=cagr
                                )
                                db.add(new_perf)
                                account_model.performance = new_perf
                            
                            await db.commit()
                            logger.info(f"Updated single account {acc['account_id']}: "
                                        f"invested_amt={invested_amt}, pf_value={pf_value}, "
                                        f"cash_value={cash_value}, total_holdings={total_holdings}, "
                                        f"total_twrr={total_twrr}")

            for joint_acc in joint_accounts:
                joint_acc_dict = {
                    'account_id': joint_acc['joint_account_id'],
                    'account_type': 'joint'
                }
                invested_amt = await cashflow_processor.calculate_invested_amt(joint_acc['joint_account_id'], 'joint')
                pf_value = await portfolio_processor.calculate_pf_value(joint_acc['joint_account_id'], 'joint')
                
                month_ends_dict = {}
                cash_value = 0.0
                for single_acc in joint_acc['single_accounts']:
                    portfolio_values, month_ends = await progression_processor.get_portfolio_values(single_acc['account_id'], 'single')
                    cash_value += await cashflow_processor.calculate_cash_value(single_acc, month_ends)
                    month_ends_dict[single_acc['account_id']] = month_ends
                total_holdings = pf_value + cash_value
    
                if month_ends_dict:
                    df_joint = await progression_processor.get_cashflow_progression_df(joint_acc_dict, month_ends_dict)

                    if not df_joint.empty:
                        await progression_processor.update_cashflow_progression_table(joint_acc_dict, df_joint)
                        logger.info(f"Updated cashflow progression for joint account {joint_acc['joint_account_id']}")

                        time_periods_df, total_twrr, current_yr_twrr, cagr = progression_processor.get_time_periods_df(df_joint)
                        await progression_processor.update_time_periods_table(joint_acc_dict, time_periods_df)

                        try:
                            account_model = await db.get(
                                JointAccount, 
                                joint_acc['joint_account_id'],
                                options=[selectinload(JointAccount.performance)])
                            if account_model:
                                account_model.invested_amt = round(invested_amt, 2)
                                account_model.pf_value = round(pf_value, 2)
                                account_model.cash_value = round(cash_value, 2)
                                account_model.total_holdings = round(total_holdings, 2)

                                if account_model.performance:
                                    account_model.performance.total_twrr = round(total_twrr, 2)
                                    account_model.performance.current_yr_twrr = round(current_yr_twrr, 2)
                                    account_model.performance.cagr = round(cagr, 2)
                                else:
                                    new_perf = AccountPerformance(
                                        performance_id=f"PERF_{joint_acc['joint_account_id']}",
                                        owner_id=joint_acc['joint_account_id'],
                                        owner_type='joint',
                                        total_twrr=total_twrr,
                                        current_yr_twrr=current_yr_twrr,
                                        cagr=cagr
                                    )
                                    db.add(new_perf)
                                    account_model.performance = new_perf
                                
                                logger.info(f"Attempting to commit updates for joint account {joint_acc['joint_account_id']}")
                                await db.commit()
                                logger.info(f"Updated joint account {joint_acc['joint_account_id']}: "
                                            f"invested_amt={invested_amt}, pf_value={pf_value}, "
                                            f"cash_value={cash_value}, total_holdings={total_holdings}, "
                                            f"total_twrr={total_twrr}")
                        except Exception as e:
                            logger.error(f"Error updating joint account {joint_acc['joint_account_id']}: {e}", exc_info=True)
                            await db.rollback()
                else:
                    logger.warning(f"Month ends dict is empty for joint account {joint_acc['joint_account_id']}, skipping df_joint generation.") # Log if month_ends_dict is empty

    except Exception as e:
        logger.error(f"Error in run function: {e}")

if __name__ == "__main__":
    asyncio.run(runner())