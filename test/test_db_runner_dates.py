import sys
import os
import asyncio
import logging
import pandas as pd
from datetime import datetime

# Add the parent directory to sys.path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from app.services.accounts.account_service import AccountService
from app.services.accounts.joint_account_service import JointAccountService
from app.scripts.data_fetchers.data_transformer import KeynoteDataTransformer, ZerodhaDataTransformer
from app.scripts.db_processors.cashflow_processor import CashflowProcessor
from app.scripts.db_processors.actual_portfolio_processor import ActualPortfolioProcessor
from app.scripts.db_processors.cashflow_progression_processor import CashflowProgressionProcessor
from app.models.accounts.account_cashflow_progression import AccountCashflowProgression
from sqlalchemy import select, func, and_, text

# Configure logging for this test
log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] (%(filename)s) %(message)s')
file_handler = logging.FileHandler('test_db_runner_dates.log') # Log to a specific file
file_handler.setFormatter(log_formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

logger = logging.getLogger('test_db_runner_dates')
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

async def test_runner_date_checks():
    """Simulates db_runner logic to check for specific dates in dataframes."""
    logger.info("Starting test: Checking for dates 2025-04-29 and 2025-04-30")
    try:
        async with AsyncSessionLocal() as db:
            accounts_data = await AccountService.get_single_accounts_with_broker_info(db)

            if not accounts_data:
                logger.warning("No single accounts found.")
                return

            joint_accounts = await JointAccountService.get_joint_accounts_with_single_accounts(db)
            if not joint_accounts:
                logger.warning("No joint accounts found.")

            logger.info(f"Simulating processing for {len(accounts_data)} single accounts")

            cashflow_processor = CashflowProcessor(db, KeynoteDataTransformer(), ZerodhaDataTransformer())
            portfolio_processor = ActualPortfolioProcessor(db, KeynoteDataTransformer(), ZerodhaDataTransformer())
            progression_processor = CashflowProgressionProcessor(db, cashflow_processor)

            # Initialize processors (important step)
            await cashflow_processor.initialize(accounts_data, joint_accounts)
            await portfolio_processor.initialize(accounts_data, joint_accounts)

            accounts_with_target_dates = {}
            target_dates_str = ["2025-04-29", "2025-04-30"]

            for acc in accounts_data:
                acc['account_type'] = 'single'
                account_id = acc['account_id']
                logger.debug(f"Processing account: {account_id}")

                try:
                    # Simulate calculations performed in db_runner
                    portfolio_values, month_ends = await progression_processor.get_portfolio_values(account_id, 'single')

                    # --- Specific check for ACC_000308 portfolio values ---
                    if account_id == "ACC_000308":
                        portfolio_dates_str = sorted([d.strftime('%Y-%m-%d') for d in portfolio_values.keys()])
                        logger.info(f"Portfolio dates for {account_id}: {portfolio_dates_str}")
                        if "2025-04-29" in portfolio_dates_str:
                            logger.info(f"Date 2025-04-29 IS present in portfolio_values for {account_id}")
                        else:
                            logger.warning(f"Date 2025-04-29 is NOT present in portfolio_values for {account_id}")
                    # --- End specific check ---

                    month_ends_dict = {account_id: month_ends}

                    if month_ends:
                        df_single = await progression_processor.get_cashflow_progression_df(acc, month_ends_dict)

                        if not df_single.empty:
                            # --- Check for target dates in the generated dataframe ---
                            df_dates_str = df_single['event_date'].astype(str).values
                            found_dates = [date for date in target_dates_str if date in df_dates_str]

                            if found_dates:
                                logger.info(f"Account {account_id} HAS dates {found_dates} in its generated dataframe (df_single)")
                                accounts_with_target_dates[account_id] = found_dates
                            else:
                                # Optional: Log if target dates are expected but not found
                                # logger.debug(f"Account {account_id} does NOT have target dates {target_dates_str} in df_single")
                                pass
                            # --- End date check ---

                            # We are NOT calling update_cashflow_progression_table here to avoid DB changes
                            logger.debug(f"Dataframe generated for {account_id}. Would normally update DB now.")

                        else:
                            logger.debug(f"Generated dataframe for {account_id} is empty.")
                    else:
                        logger.debug(f"No month_ends found for {account_id}.")

                except Exception as e:
                    logger.error(f"Error processing account {account_id}: {e}", exc_info=True)

            logger.info("--- Summary of Accounts with Target Dates in Generated DataFrames ---")
            if accounts_with_target_dates:
                for acc_id, dates in accounts_with_target_dates.items():
                    logger.info(f"Account: {acc_id}, Found Dates: {dates}")
            else:
                logger.info("No accounts found with the target dates (2025-04-29, 2025-04-30) in their generated dataframes.")
            logger.info("--- End Summary ---")

    except Exception as e:
        logger.error(f"Error in test_runner_date_checks: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_runner_date_checks())
