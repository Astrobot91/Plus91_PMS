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

# Configure logging
log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
file_handler = logging.FileHandler('account_date_analysis.log')
file_handler.setFormatter(log_formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

logger = logging.getLogger('account_date_analysis')
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

async def check_account_cashflow_progression(account_id):
    """Check the current data in the account_cashflow_progression table for the account"""
    async with AsyncSessionLocal() as db:
        # Query existing progression data
        stmt = select(AccountCashflowProgression).where(
            and_(
                AccountCashflowProgression.owner_id == account_id,
                AccountCashflowProgression.owner_type == 'single'
            )
        ).order_by(AccountCashflowProgression.event_date)
        
        result = await db.execute(stmt)
        existing_data = result.scalars().all()
        
        logger.info(f"Found {len(existing_data)} existing progression entries for {account_id}")
        
        # Print the last few entries
        if existing_data:
            last_entries = existing_data[-3:] if len(existing_data) >= 3 else existing_data
            for entry in last_entries:
                logger.info(f"Existing entry: {entry.event_date} - CF: {entry.cashflow}, PF: {entry.portfolio_value}")
        else:
            logger.info(f"No existing progression entries found for {account_id}")

async def generate_progression_df_single_account():
    """Generate progression dataframe for just ACC_000308"""
    async with AsyncSessionLocal() as db:
        account_data = [
            {
                "account_id": "ACC_000308",
                "broker_name": "zerodha",
                "broker_code": "BLQ476",
                "acc_start_date": "2022-02-01",
                "account_type": "single"
            }
        ]
        
        cashflow_processor = CashflowProcessor(db, KeynoteDataTransformer(), ZerodhaDataTransformer())
        portfolio_processor = ActualPortfolioProcessor(db, KeynoteDataTransformer(), ZerodhaDataTransformer())
        progression_processor = CashflowProgressionProcessor(db, cashflow_processor)
        
        # Initialize processors
        await cashflow_processor.initialize(account_data, [])
        await portfolio_processor.initialize(account_data, [])
        
        # Get portfolio values and month ends
        acc = account_data[0]
        portfolio_values, month_ends = await progression_processor.get_portfolio_values(acc['account_id'], 'single')
        
        # Generate month_ends_dict
        month_ends_dict = {acc['account_id']: month_ends}
        
        # Log month_ends
        logger.info(f"Month ends for single account run: {sorted(month_ends)}")
        
        # Generate progression dataframe
        df_single = await progression_processor.get_cashflow_progression_df(acc, month_ends_dict)
        
        # Log dataframe
        logger.info("Progression dataframe for single account run:")
        if not df_single.empty:
            logger.info(f"DataFrame has {len(df_single)} rows")
            logger.info(f"Last 5 rows:\n{df_single.tail(5)}")
            logger.info(f"All dates in dataframe: {df_single['event_date'].tolist()}")
            # Check for specific date
            if '2025-04-29' in df_single['event_date'].astype(str).values:
                logger.info("Date 2025-04-29 IS present in the dataframe")
            else:
                logger.info("Date 2025-04-29 is NOT present in the dataframe")
        else:
            logger.info("DataFrame is empty")
        
        return df_single

async def generate_progression_df_all_accounts():
    """Generate progression dataframe for all accounts, focusing on ACC_000308"""
    async with AsyncSessionLocal() as db:
        # Get all accounts
        all_accounts = await AccountService.get_single_accounts_with_broker_info(db)
        
        if not all_accounts:
            logger.warning("No single accounts found.")
            return None
        
        logger.info(f"Found {len(all_accounts)} accounts in total")
        
        # Log accounts
        target_account = None
        for account in all_accounts:
            if account["account_id"] == "ACC_000308":
                target_account = account
                logger.info(f"Found target account: {account}")
        
        if not target_account:
            logger.warning("Target account ACC_000308 not found in accounts list")
            return None
        
        # Add account_type
        for acc in all_accounts:
            acc['account_type'] = 'single'
        
        # Initialize processors
        cashflow_processor = CashflowProcessor(db, KeynoteDataTransformer(), ZerodhaDataTransformer())
        portfolio_processor = ActualPortfolioProcessor(db, KeynoteDataTransformer(), ZerodhaDataTransformer())
        progression_processor = CashflowProgressionProcessor(db, cashflow_processor)
        
        # Initialize with all accounts
        await cashflow_processor.initialize(all_accounts, [])
        await portfolio_processor.initialize(all_accounts, [])
        
        # Get portfolio values and month ends for just the target account
        target_account['account_type'] = 'single'  # Ensure account_type is set
        portfolio_values, month_ends = await progression_processor.get_portfolio_values(target_account['account_id'], 'single')
        
        # Log month_ends
        logger.info(f"Month ends for all-accounts run: {sorted(month_ends)}")
        
        # Generate month_ends_dict
        month_ends_dict = {target_account['account_id']: month_ends}
        
        # Generate progression dataframe
        df_all = await progression_processor.get_cashflow_progression_df(target_account, month_ends_dict)
        
        # Log dataframe
        logger.info("Progression dataframe for all-accounts run:")
        if not df_all.empty:
            logger.info(f"DataFrame has {len(df_all)} rows")
            logger.info(f"Last 5 rows:\n{df_all.tail(5)}")
            logger.info(f"All dates in dataframe: {df_all['event_date'].tolist()}")
            # Check for specific date
            if '2025-04-29' in df_all['event_date'].astype(str).values:
                logger.info("Date 2025-04-29 IS present in the dataframe")
            else:
                logger.info("Date 2025-04-29 is NOT present in the dataframe")
        else:
            logger.info("DataFrame is empty")
        
        return df_all

async def check_portfolio_actual_table():
    """Check the account_actual_portfolio table for latest dates"""
    async with AsyncSessionLocal() as db:
        # Query the max date for each account
        query = text("""
            SELECT owner_id, MAX(snapshot_date) as max_date
            FROM account_actual_portfolio
            WHERE owner_type = 'single'
            GROUP BY owner_id
            ORDER BY owner_id
        """)
        
        result = await db.execute(query)
        dates_by_account = result.fetchall()
        
        logger.info(f"Found max dates for {len(dates_by_account)} accounts in portfolio table")
        
        # Check target account
        for account_id, max_date in dates_by_account:
            if account_id == "ACC_000308":
                logger.info(f"Max date for ACC_000308 in actual_portfolio: {max_date}")
                
                # Get all entries for this account on the max date
                entries_query = text("""
                    SELECT trading_symbol, quantity, market_value
                    FROM account_actual_portfolio
                    WHERE owner_id = 'ACC_000308' 
                    AND owner_type = 'single'
                    AND snapshot_date = :max_date
                """)
                
                entries_result = await db.execute(entries_query, {"max_date": max_date})
                entries = entries_result.fetchall()
                
                logger.info(f"Found {len(entries)} entries for ACC_000308 on {max_date}")
                for i, (symbol, qty, market_value) in enumerate(entries[:5]):  # Show first 5
                    logger.info(f"Entry {i+1}: {symbol}, Qty: {qty}, Value: {market_value}")

async def analyze_get_portfolio_values_function():
    """Deep dive into the get_portfolio_values function to see why it might be different"""
    async with AsyncSessionLocal() as db:
        # Try with a clean implementation of get_portfolio_values
        logger.info("Analyzing the get_portfolio_values function behavior")
        
        # Get portfolio values direct from SQL
        query = text("""
            SELECT snapshot_date, SUM(market_value) as total_value
            FROM account_actual_portfolio
            WHERE owner_id = 'ACC_000308' AND owner_type = 'single'
            GROUP BY snapshot_date
            ORDER BY snapshot_date
        """)
        
        result = await db.execute(query)
        portfolio_dates = result.fetchall()
        
        logger.info(f"Direct SQL query found {len(portfolio_dates)} portfolio dates")
        logger.info(f"Latest 5 dates from direct SQL:")
        for date, value in portfolio_dates[-5:]:
            logger.info(f"Date: {date}, Value: {value}")
        
        # Try the same using the actual function from the processor
        cashflow_processor = CashflowProcessor(db, KeynoteDataTransformer(), ZerodhaDataTransformer())
        progression_processor = CashflowProgressionProcessor(db, cashflow_processor)
        
        portfolio_values, month_ends = await progression_processor.get_portfolio_values("ACC_000308", 'single')
        
        logger.info("Portfolio values from processor function:")
        for date, value in list(portfolio_values.items())[-5:]:
            logger.info(f"Date: {date}, Value: {value}")
        
        logger.info("Month ends from processor function:")
        logger.info(f"Total month_ends: {len(month_ends)}")
        logger.info(f"Latest 5 month_ends: {sorted(month_ends)[-5:]}")

async def main():
    """Main function to diagnose the issue"""
    logger.info("Starting account date analysis")
    
    # Check current data in the table
    await check_account_cashflow_progression("ACC_000308")
    
    # Check the actual portfolio table
    await check_portfolio_actual_table()
    
    # Analyze the get_portfolio_values function
    await analyze_get_portfolio_values_function()
    
    # Generate single account DF
    logger.info("\n==== RUNNING WITH SINGLE ACCOUNT ====\n")
    df_single = await generate_progression_df_single_account()
    
    # Generate all accounts DF
    logger.info("\n==== RUNNING WITH ALL ACCOUNTS ====\n")
    df_all = await generate_progression_df_all_accounts()
    
    # Compare dataframes if both are available
    if df_single is not None and df_all is not None and not df_single.empty and not df_all.empty:
        logger.info("\n==== COMPARING DATAFRAMES ====\n")
        
        # Convert dates for proper comparison
        df_single['event_date'] = pd.to_datetime(df_single['event_date'])
        df_all['event_date'] = pd.to_datetime(df_all['event_date'])
        
        # Sort by date
        df_single = df_single.sort_values('event_date')
        df_all = df_all.sort_values('event_date')
        
        # Check for differences in dates
        single_dates = set(df_single['event_date'])
        all_dates = set(df_all['event_date'])
        
        dates_only_in_single = single_dates - all_dates
        dates_only_in_all = all_dates - single_dates
        
        logger.info(f"Dates only in single run: {sorted(dates_only_in_single)}")
        logger.info(f"Dates only in all-accounts run: {sorted(dates_only_in_all)}")
        
        # Check if 2025-04-29 is in each
        specific_date = pd.to_datetime('2025-04-29')
        logger.info(f"2025-04-29 in single run: {specific_date in single_dates}")
        logger.info(f"2025-04-29 in all-accounts run: {specific_date in all_dates}")
        
        # Compare specific periods
        logger.info("Last entries in single run:")
        logger.info(df_single.tail(3))
        
        logger.info("Last entries in all-accounts run:")
        logger.info(df_all.tail(3))

if __name__ == "__main__":
    asyncio.run(main())