import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.accounts.account_actual_portfolio import AccountActualPortfolio
from app.database import AsyncSessionLocal
from typing import List, Tuple

# Temporary basic logging setup (replace with app.logger if preferred)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HistStockPriceUpdater:
    def __init__(self):
        """Initialize the HistStockPriceUpdater."""
        logger.info("Initializing HistStockPriceUpdater")

    async def get_unique_symbol_dates(self, db: AsyncSession) -> List[Tuple[str, str]]:
        """
        Retrieve all unique combinations of trading_symbol and snapshot_date from account_actual_portfolio.

        Args:
            db (AsyncSession): The asynchronous database session.

        Returns:
            List[Tuple[str, str]]: A list of tuples containing (trading_symbol, snapshot_date).
        """
        logger.info("Fetching unique trading_symbol and snapshot_date combinations")
        try:
            query = select(
                AccountActualPortfolio.trading_symbol,
                AccountActualPortfolio.snapshot_date
            ).distinct()
            logger.debug("Executing query")
            result = await db.execute(query)
            symbol_date_pairs = result.all()
            logger.debug(f"Raw result count: {len(symbol_date_pairs)}")
            processed_pairs = [(symbol, str(date) if date else "1970-01-01") for symbol, date in symbol_date_pairs]
            logger.info(f"Processed {len(processed_pairs)} unique pairs")
            return processed_pairs
        except Exception as e:
            logger.error(f"Error in get_unique_symbol_dates: {str(e)}", exc_info=True)
            raise

async def main() -> None:
    """Main function to test the query."""
    logger.info("Starting main function")
    try:
        async with AsyncSessionLocal() as db:
            logger.info("Database session opened")
            updater = HistStockPriceUpdater()
            symbol_date_pairs = await updater.get_unique_symbol_dates(db)
            logger.info(f"Sample of unique pairs (first 5): {symbol_date_pairs[:5]}")
            logger.info(f"Total unique pairs retrieved: {len(symbol_date_pairs)}")
    except Exception as e:
        logger.error(f"Main failed: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("Main completed")

if __name__ == "__main__":
    asyncio.run(main())