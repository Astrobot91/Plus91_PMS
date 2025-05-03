import sys
import os
import asyncio
import logging
from sqlalchemy import select, func, event
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

# Add the parent directory to sys.path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal, async_engine as engine
from app.models.accounts.account_actual_portfolio import AccountActualPortfolio
from app.services.accounts.account_service import AccountService
from app.scripts.db_processors.actual_portfolio_processor import ActualPortfolioProcessor
from app.scripts.data_fetchers.data_transformer import KeynoteDataTransformer, ZerodhaDataTransformer

# Configure logging
log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
file_handler = logging.FileHandler('rollback_analyzer.log')
file_handler.setFormatter(log_formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

logger = logging.getLogger('rollback_analyzer')
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Create tracking for SQLAlchemy events
tracked_rollbacks = []

@event.listens_for(engine.sync_engine, "rollback")
def receive_rollback(conn):
    """Track database rollbacks"""
    import traceback
    stack = traceback.extract_stack()
    stack_info = "".join(traceback.format_list(stack[-6:-1]))  # Get last 5 frames
    
    tracked_rollbacks.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stack_trace": stack_info
    })
    
    logger.warning(f"ROLLBACK detected! Stack trace:\n{stack_info}")

async def analyze_account_portfolio_value(account_id, account_type='single'):
    """Analyze portfolio value calculation and potential rollback causes"""
    logger.info(f"Analyzing portfolio value for account {account_id} ({account_type})")
    
    async with AsyncSessionLocal() as db:
        # Get the latest snapshot date
        latest_date_query = select(func.max(AccountActualPortfolio.snapshot_date)).where(
            AccountActualPortfolio.owner_id == account_id,
            AccountActualPortfolio.owner_type == account_type
        )
        latest_date = (await db.execute(latest_date_query)).scalar()
        
        if latest_date:
            logger.info(f"Latest snapshot date found: {latest_date}")
            
            # Get all entries for this snapshot date
            entries_query = select(AccountActualPortfolio).where(
                AccountActualPortfolio.owner_id == account_id,
                AccountActualPortfolio.owner_type == account_type,
                AccountActualPortfolio.snapshot_date == latest_date
            )
            result = await db.execute(entries_query)
            entries = result.scalars().all()
            
            logger.info(f"Found {len(entries)} portfolio entries for date {latest_date}")
            
            if entries:
                # Inspect entries
                for i, entry in enumerate(entries[:5]):  # Show the first 5 entries
                    logger.info(f"Entry {i+1}: {entry.trading_symbol}, Quantity: {entry.quantity}, Market Value: {entry.market_value}")
                
                # Calculate sum
                sum_query = select(func.sum(AccountActualPortfolio.market_value)).where(
                    AccountActualPortfolio.owner_id == account_id,
                    AccountActualPortfolio.owner_type == account_type,
                    AccountActualPortfolio.snapshot_date == latest_date
                )
                sum_result = await db.execute(sum_query)
                sum_value = sum_result.scalar()
                
                logger.info(f"Calculated sum of market values: {sum_value}")
                
                # Now run the actual function that might cause rollbacks
                try:
                    processor = ActualPortfolioProcessor(db, KeynoteDataTransformer(), ZerodhaDataTransformer())
                    result = await processor.calculate_pf_value(account_id, account_type)
                    logger.info(f"calculate_pf_value returned: {result}")
                except Exception as e:
                    logger.error(f"Exception during calculate_pf_value: {e}")
            else:
                logger.warning(f"No portfolio entries found for date {latest_date}")
        else:
            logger.warning(f"No snapshot dates found for account {account_id}")

async def run_analysis_for_all_accounts():
    """Run analysis for all accounts that have rollbacks"""
    # These are the account IDs observed to have rollbacks in the logs
    problematic_accounts = [
        "ACC_000387", "ACC_000388", "ACC_000389", "ACC_000392", 
        "ACC_000393", "ACC_000394", "ACC_000396", "ACC_000397",
        "ACC_000398", "ACC_000399", "ACC_000400", "ACC_000401", 
        "ACC_000402", "ACC_000505", "ACC_000323", "ACC_000374",
        "ACC_000382", "ACC_000385"
    ]
    
    logger.info(f"Starting analysis for {len(problematic_accounts)} accounts")
    
    async with AsyncSessionLocal() as db:
        # Verify these accounts exist in the database
        for account_id in problematic_accounts:
            logger.info(f"\n{'='*50}\nAnalyzing account {account_id}\n{'='*50}")
            await analyze_account_portfolio_value(account_id)

async def detail_analyze_rollback_patterns():
    """Analyze common patterns in rollbacks across accounts"""
    logger.info("Starting detailed analysis of rollback patterns")
    
    # These are the account IDs observed to have rollbacks in the logs
    problematic_accounts = [
        "ACC_000387", "ACC_000388", "ACC_000389", "ACC_000392", 
        "ACC_000393", "ACC_000394"
    ]  # Testing with a small subset
    
    async with AsyncSessionLocal() as db:
        # Look at the portfolio data structure
        issues = []
        
        for account_id in problematic_accounts:
            logger.info(f"Analyzing rollback patterns for account {account_id}")
            
            # Get all snapshot dates for this account
            dates_query = select(AccountActualPortfolio.snapshot_date).where(
                AccountActualPortfolio.owner_id == account_id,
                AccountActualPortfolio.owner_type == 'single'
            ).distinct().order_by(AccountActualPortfolio.snapshot_date.desc())
            
            result = await db.execute(dates_query)
            snapshot_dates = result.scalars().all()
            
            logger.info(f"Found {len(snapshot_dates)} snapshot dates")
            
            if snapshot_dates:
                # Check most recent snapshot
                latest_date = snapshot_dates[0]
                
                # Get entries for latest date
                entries_query = select(AccountActualPortfolio).where(
                    AccountActualPortfolio.owner_id == account_id,
                    AccountActualPortfolio.owner_type == 'single',
                    AccountActualPortfolio.snapshot_date == latest_date
                )
                
                result = await db.execute(entries_query)
                entries = result.scalars().all()
                
                logger.info(f"Latest date: {latest_date}, entries: {len(entries)}")
                
                # Look for unusual values
                null_entries = 0
                zero_qty_entries = 0
                negative_entries = 0
                placeholder_entries = 0
                
                for entry in entries:
                    if entry.market_value is None:
                        null_entries += 1
                    if entry.quantity == 0:
                        zero_qty_entries += 1
                    if entry.market_value < 0:
                        negative_entries += 1
                    if entry.trading_symbol == "place holder":
                        placeholder_entries += 1
                
                account_issues = {
                    "account_id": account_id,
                    "latest_date": latest_date,
                    "total_entries": len(entries),
                    "null_entries": null_entries,
                    "zero_qty": zero_qty_entries,
                    "negative": negative_entries,
                    "placeholders": placeholder_entries
                }
                
                logger.info(f"Issues found: {account_issues}")
                issues.append(account_issues)
        
        # Summarize findings
        if issues:
            logger.info("\nSummary of issues across accounts:")
            for account_issue in issues:
                logger.info(f"{account_issue['account_id']}: {account_issue['total_entries']} entries, " +
                            f"{account_issue['null_entries']} nulls, {account_issue['zero_qty']} zeros, " +
                            f"{account_issue['negative']} negative, {account_issue['placeholders']} placeholders")

async def main():
    """Main function to run rollback analysis"""
    logger.info("Starting rollback analyzer")
    
    # Run analysis for problematic accounts
    await run_analysis_for_all_accounts()
    
    # Detailed analysis of rollback patterns
    await detail_analyze_rollback_patterns()
    
    # Report rollbacks collected during execution
    if tracked_rollbacks:
        logger.info(f"\nCaptured {len(tracked_rollbacks)} rollbacks during execution")
        for i, rb in enumerate(tracked_rollbacks):
            logger.info(f"\nRollback {i+1} at {rb['timestamp']}:\n{rb['stack_trace']}")
    else:
        logger.info("No rollbacks were captured during execution")

if __name__ == "__main__":
    asyncio.run(main())