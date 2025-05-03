import sys
import asyncio
import os
import glob
import pandas as pd
from sqlalchemy import select, union, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.stock_ltps import StockLTP
from app.models.accounts.account_actual_portfolio import AccountActualPortfolio
from app.models.portfolio.basket_stock_mapping import BasketStockMapping
from app.scripts.data_fetchers.broker_data import BrokerData
from typing import List, Dict, Any
from app.database import AsyncSessionLocal
from datetime import datetime
from app.logger import logger


class LtpProcessor:
    def __init__(self, broker: str):
        """Initialize the LtpProcessor."""
        self.broker = broker
        logger.info("Initializing LtpProcessor")

    def get_latest_outside_holdings_file(self) -> str:
        """
        Get the path of the latest Outside holdings file based on the date in filename.
        
        Returns:
            str: Path to the latest Outside holdings file, or None if no files exist
        """
        pattern = "/home/admin/Plus91Backoffice/Forked_Plus91_Backend/data/other_holdings/Outside_holdings_*.xlsx"
        files = glob.glob(pattern)
        
        if not files:
            logger.debug("No Outside holdings files found - continuing without them")
            return None
            
        # Extract dates from filenames and find latest
        latest_file = max(files, key=lambda f: datetime.strptime(f.split("Outside_holdings_")[1].replace(".xlsx", ""), "%Y-%m-%d"))
        logger.debug(f"Latest Outside holdings file: {latest_file}")
        return latest_file

    def get_outside_holdings_symbols(self) -> List[str]:
        """
        Read trading symbols from the latest Outside holdings file.
        
        Returns:
            List[str]: List of trading symbols from Outside holdings, or empty list if no file exists
        """
        try:
            latest_file = self.get_latest_outside_holdings_file()
            if not latest_file:
                logger.debug("Proceeding without Outside holdings symbols")
                return []
                
            df = pd.read_excel(latest_file)
            if 'trading_symbol' not in df.columns:
                logger.warning("No trading_symbol column found in Outside holdings file - proceeding without these symbols")
                return []
                
            symbols = df['trading_symbol'].unique().tolist()
            logger.debug(f"Retrieved {len(symbols)} trading symbols from Outside holdings")
            return symbols
        except Exception as e:
            logger.warning(f"Error reading Outside holdings file: {str(e)} - proceeding without these symbols")
            return []

    async def get_trading_symbols(self, db: AsyncSession) -> List[str]:
        """
        Retrieve unique trading symbols from all available sources:
        - account_actual_portfolio
        - account_ideal_portfolio
        - latest Outside holdings file (if available)

        Args:
            db (AsyncSession): The asynchronous database session to execute the query.

        Returns:
            List[str]: A list of unique trading symbols.
        """
        logger.info("Fetching unique trading symbols from all sources")
        try:
            # Get symbols from portfolios
            actual_symbols = select(AccountActualPortfolio.trading_symbol)
            ideal_symbols = select(BasketStockMapping.trading_symbol)
            unique_symbols_query = union(actual_symbols, ideal_symbols)
            result = await db.execute(unique_symbols_query)
            db_symbols = result.scalars().all()
            logger.debug(f"Retrieved {len(db_symbols)} symbols from portfolios")
            
            # Get symbols from Outside holdings (if available)
            outside_symbols = self.get_outside_holdings_symbols()
            if outside_symbols:
                logger.debug(f"Adding {len(outside_symbols)} symbols from Outside holdings")
            
            # Combine all symbols and make unique
            all_symbols = list(set(db_symbols + outside_symbols))
            
            logger.info(f"Total {len(all_symbols)} unique trading symbols from all available sources")
            return all_symbols
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
            upstox_master_data = BrokerData.get_master_data(broker_type=self.broker)
            if upstox_master_data.get("status") != "success":
                logger.error("Failed to fetch master data from broker")
                raise ValueError("Failed to fetch master data from broker")
        
            logger.debug("Processing master data into DataFrame")
            upstox_master_df = pd.DataFrame(upstox_master_data["data"])
            print(upstox_master_df)
            upstox_master_df_slice = upstox_master_df[
                (upstox_master_df["exchange"].isin(["NSE_EQ", "BSE_EQ"]))
            ][["tradingsymbol", "exchange", "exchange_token"]]

            upstox_master_df_slice_sorted = upstox_master_df_slice.sort_values(
                by=["tradingsymbol", "exchange"],
                ascending=[True, True]
            )
            upstox_master_df_slice = upstox_master_df_slice_sorted.drop_duplicates(
                subset="tradingsymbol", keep="first"
            )
            mapping_data = upstox_master_df_slice[
                upstox_master_df_slice["tradingsymbol"].isin(trading_symbols)
            ]
            mapping_data[['exchange', 'instrument_type']] = mapping_data['exchange'].str.split('_', expand=True)
            mapping_data["exchange"] = mapping_data["exchange"].astype(str)
            mapping_data["instrument_type"] = mapping_data["instrument_type"].astype(str)
            mapping_data["exchange_token"] = mapping_data["exchange_token"].astype(str)
            mapping_data.reset_index(drop=True, inplace=True)

            ltp_request_data = mapping_data[["exchange_token", "exchange", "instrument_type"]].to_dict(orient="records")

            logger.debug(f"Requesting LTP quotes for {len(ltp_request_data)} symbols")
            ltp_response_data = BrokerData.get_ltp_quote(self.broker, ltp_request_data)
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
        processor = LtpProcessor(broker='upstox')
        await processor.process_ltps(db)
    logger.info("Main LTP processing script completed")


if __name__ == "__main__":
    asyncio.run(main())