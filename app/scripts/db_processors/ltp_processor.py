import asyncio
import pandas as pd
from sqlalchemy import select, union, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.stock_ltps import StockLTP
from app.models.accounts.account_actual_portfolio import AccountActualPortfolio
from app.models.accounts.account_ideal_portfolio import AccountIdealPortfolio
from app.scripts.data_fetchers.broker_data import BrokerData
from typing import List, Dict, Any
from app.database import AsyncSessionLocal
from datetime import datetime
from app.logger import logger


class LtpProcessor:
    def __init__(self):
        """Initialize the LtpProcessor."""
        logger.info("Initializing LtpProcessor")

    async def get_trading_symbols(self, db: AsyncSession) -> List[str]:
        """
        Retrieve all unique trading symbols from account_actual_portfolio and account_ideal_portfolio tables.

        Args:
            db (AsyncSession): The asynchronous database session to execute the query.

        Returns:
            List[str]: A list of unique trading symbols.
        """
        logger.info("Fetching unique trading symbols from database")
        try:
            actual_symbols = select(AccountActualPortfolio.trading_symbol)
            ideal_symbols = select(AccountIdealPortfolio.trading_symbol)
            unique_symbols_query = union(actual_symbols, ideal_symbols)
            result = await db.execute(unique_symbols_query)
            unique_symbols = result.scalars().all()
            logger.debug(f"Retrieved {len(unique_symbols)} unique trading symbols")
            return unique_symbols
        except Exception as e:
            logger.error(f"Error fetching trading symbols: {str(e)}")
            raise

    async def get_ltps(self, trading_symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch Last Traded Prices (LTPs) for the given trading symbols from the broker.

        Args:
            trading_symbols (List[str]): List of trading symbols to fetch LTPs for.

        Returns:
            List[Dict[str, Any]]: List of dictionaries containing 'trading_symbol' and 'ltp'.
        
        Raises:
            ValueError: If fetching master data or LTP quotes from the broker fails.
        """
        logger.info(f"Fetching LTPs for {len(trading_symbols)} trading symbols")
        try:
            upstox_master_data = BrokerData.get_master_data()
            if upstox_master_data.get("status") != "success":
                logger.error("Failed to fetch master data from broker")
                raise ValueError("Failed to fetch master data from broker")

            logger.debug("Processing master data into DataFrame")
            upstox_master_df = pd.DataFrame(upstox_master_data["data"])

            upstox_master_df_slice = upstox_master_df[
                (upstox_master_df["exchange"].isin(["NSE", "BSE"])) &
                (upstox_master_df["instrument_type"] == "EQ")
            ][["trading_symbol", "exchange", "exchange_token", "instrument_type"]]
            
            upstox_master_df_slice_sorted = upstox_master_df_slice.sort_values(
                by=["trading_symbol", "exchange"],
                ascending=[True, True]
            )
            upstox_master_df_slice = upstox_master_df_slice_sorted.drop_duplicates(
                subset="trading_symbol", keep="first"
            )
            mapping_data = upstox_master_df_slice[
                upstox_master_df_slice["trading_symbol"].isin(trading_symbols)
            ]
            mapping_data.reset_index(drop=True, inplace=True)
            ltp_request_data = mapping_data[["exchange_token", "exchange", "instrument_type"]].to_dict(orient="records")
            
            logger.debug(f"Requesting LTP quotes for {len(ltp_request_data)} symbols")
            ltp_response_data = BrokerData.get_ltp_quote(ltp_request_data)
            if ltp_response_data.get("status") != "success":
                logger.error("Failed to fetch LTP quotes from broker")
                raise ValueError("Failed to fetch LTP quotes from broker")
            ltp_response_data = ltp_response_data["data"]
            
            trading_symbols_list = []
            ltps_list = []
            for key in ltp_response_data:
                trading_symbols_list.append(ltp_response_data[key]["trading_symbol"])
                ltps_list.append(ltp_response_data[key]["last_price"])

            trading_symbol_ltp = pd.DataFrame({
                "trading_symbol": trading_symbols_list,
                "ltp": ltps_list
            })
            ltp_data = trading_symbol_ltp.to_dict(orient="records")
            logger.info(f"Successfully fetched LTPs for {len(ltp_data)} symbols")
            return ltp_data
        except Exception as e:
            logger.error(f"Error fetching LTPs: {str(e)}")
            raise

    async def delete_existing_ltps(self, db: AsyncSession) -> None:
        """
        Delete all existing rows from the stock_ltps table.

        Args:
            db (AsyncSession): The asynchronous database session.
        """
        logger.info("Deleting existing LTPs from stock_ltps table")
        try:
            await db.execute(delete(StockLTP))
            await db.commit()
            logger.debug("Successfully deleted existing LTPs")
        except Exception as e:
            logger.error(f"Error deleting existing LTPs: {str(e)}")
            raise

    async def insert_ltps(self, db: AsyncSession, ltp_data: List[Dict[str, Any]]) -> None:
        """
        Insert new LTP data into the stock_ltps table.

        Args:
            db (AsyncSession): The asynchronous database session.
            ltp_data (List[Dict[str, Any]]): List of dictionaries with 'trading_symbol' and 'ltp'.
        """
        if ltp_data:
            logger.info(f"Inserting {len(ltp_data)} new LTP records into stock_ltps table")
            try:
                async with db.begin():
                    await db.execute(
                        insert(StockLTP),
                        [
                            {
                                "trading_symbol": item["trading_symbol"],
                                "ltp": item["ltp"],
                            }
                            for item in ltp_data
                        ]
                    )
                logger.debug("Successfully inserted new LTPs")
            except Exception as e:
                logger.error(f"Error inserting LTPs: {str(e)}")
                raise
        else:
            logger.warning("No LTP data to insert")

    async def process_ltps(self, db: AsyncSession) -> None:
        """
        Process the entire LTP update: fetch symbols, get LTPs, delete existing data, and insert new data.

        Args:
            db (AsyncSession): The asynchronous database session.
        """
        logger.info("Starting LTP processing")
        try:
            symbols = await self.get_trading_symbols(db)
            ltp_data = await self.get_ltps(symbols)
            await self.delete_existing_ltps(db)
            await self.insert_ltps(db, ltp_data)
            logger.info("LTP processing completed successfully")
        except Exception as e:
            logger.error(f"LTP processing failed: {str(e)}")
            raise


async def main() -> None:
    """Main function to run the LTP processing."""
    logger.info("Starting main LTP processing script")
    async with AsyncSessionLocal() as db:
        processor = LtpProcessor()
        await processor.process_ltps(db)
    logger.info("Main LTP processing script completed")


if __name__ == "__main__":
    asyncio.run(main())