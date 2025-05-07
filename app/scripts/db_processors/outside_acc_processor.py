import asyncio
import os
import sys
import glob
import pandas as pd
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import and_, or_, func
from sqlalchemy.sql.expression import extract
from app.models.stock_ltps import StockLTP
from app.models.accounts.account_actual_portfolio import AccountActualPortfolio
from app.models.accounts.single_account import SingleAccount
from app.models.accounts.joint_account import JointAccount
from app.models.clients.client_details import Client
from app.models.clients.broker_details import Broker
from app.services.accounts.joint_account_service import JointAccountService
from app.database import AsyncSessionLocal
from app.logger import logger
from typing import Dict, List, Tuple, Optional


class OutsideAccProcessor:
    def __init__(self):
        """Initialize the OutsideAccProcessor."""
        logger.info("Initializing OutsideAccProcessor")
        self.ltps = {}  # Cache for LTPs
        self.joint_acc_service = JointAccountService()

    def get_latest_outside_holdings_file(self) -> Optional[Tuple[str, datetime]]:
        """
        Get the path and date of the latest Outside holdings file.
        
        Returns:
            Tuple[str, datetime]: Path to the latest file and its date, or None if no files exist
        """
        pattern = "/home/admin/Plus91Backoffice/Plus91_Backend/data/other_holdings/Outside_holdings_*.xlsx"
        files = glob.glob(pattern)
        
        if not files:
            logger.debug("No Outside holdings files found - continuing without them")
            return None
            
        # Extract dates from filenames and find latest
        latest_file = max(files, key=lambda f: datetime.strptime(f.split("Outside_holdings_")[1].replace(".xlsx", ""), "%Y-%m-%d"))
        file_date = datetime.strptime(latest_file.split("Outside_holdings_")[1].replace(".xlsx", ""), "%Y-%m-%d")
        logger.debug(f"Latest Outside holdings file: {latest_file} with date {file_date}")
        return latest_file, file_date

    async def load_ltps(self, db: AsyncSession) -> None:
        """Load all LTPs from stock_ltps table into memory."""
        logger.info("Loading LTPs from database")
        try:
            result = await db.execute(
                select(StockLTP.trading_symbol, StockLTP.ltp)
            )
            ltps = result.all()
            self.ltps = {row[0]: row[1] for row in ltps}  # row[0] is trading_symbol, row[1] is ltp
            logger.debug(f"Loaded {len(self.ltps)} LTPs")
        except Exception as e:
            logger.error(f"Error loading LTPs: {str(e)}")
            raise

    def get_cash_value(self, cash_df: pd.DataFrame, broker_code: str) -> float:
        """
        Get cash value for a broker code from cash DataFrame.
        Handles multiple entries by summing them.
        
        Args:
            cash_df: DataFrame with cash values
            broker_code: Broker code to look up
            
        Returns:
            float: Total cash value for the broker code, 0 if not found
        """
        try:
            # Get all rows for this broker_code and sum cash_values
            cash_rows = cash_df[cash_df['broker_code'] == broker_code]
            if cash_rows.empty:
                logger.debug(f"No cash value found for broker_code {broker_code}")
                return 0.0
                
            total_cash = cash_rows['cash_value'].sum()
            logger.debug(f"Found total cash value {total_cash} for broker_code {broker_code}")
            return float(total_cash)
            
        except Exception as e:
            logger.warning(f"Error getting cash value for broker_code {broker_code}: {str(e)}")
            return 0.0

    def calculate_market_value(self, holdings_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate market value for holdings using cached LTPs.
        
        Args:
            holdings_df: DataFrame with trading_symbol and quantity columns
            
        Returns:
            DataFrame with added market_value column
        """
        logger.debug("Calculating market values")
        def get_market_value(row):
            ltp = self.ltps.get(row['trading_symbol'], 0)
            return row['quantity'] * ltp

        holdings_df['market_value'] = holdings_df.apply(get_market_value, axis=1)
        return holdings_df

    async def get_latest_snapshot_month(self, db: AsyncSession, account_id: str, file_date: datetime) -> Optional[datetime]:
        """
        Get the latest snapshot date for the given account in the same month as file_date.
        
        Args:
            db: Database session
            account_id: Account ID to check
            file_date: Date from the holdings file
            
        Returns:
            Latest snapshot date in the same month if exists, else None
        """
        result = await db.execute(
            select(AccountActualPortfolio.snapshot_date)
            .where(
                and_(
                    AccountActualPortfolio.owner_id == account_id,
                    extract('year', AccountActualPortfolio.snapshot_date) == file_date.year,
                    extract('month', AccountActualPortfolio.snapshot_date) == file_date.month
                )
            )
            .distinct()
        )
        dates = result.scalars().all()
        return max(dates) if dates else None

    async def process_single_account(self, db: AsyncSession, holdings_df: pd.DataFrame, 
                                  broker_code: str, file_date: datetime,
                                  cash_df: pd.DataFrame) -> None:
        """Process holdings for a single account."""
        try:
            # Get single account ID from broker code
            result = await db.execute(
                select(SingleAccount)
                .join(Client, SingleAccount.single_account_id == Client.account_id)
                .where(Client.broker_code == broker_code.upper().strip())
            )
            account = result.scalar_one_or_none()
            
            if not account:
                logger.warning(f"No single account found for broker code {broker_code}")
                return

            # Get cash value - use case-insensitive matching
            cash_value = self.get_cash_value(cash_df, broker_code)
            logger.debug(f"Cash value for {broker_code}: {cash_value}")

            # Calculate market values with case-insensitive matching
            # First try exact match
            account_holdings = holdings_df[holdings_df['broker_code'] == broker_code].copy()    
            # If no matches found, try case-insensitive match
            if account_holdings.empty:
                logger.info(f"No exact match for broker code {broker_code}, trying case-insensitive match")
                account_holdings = holdings_df[holdings_df['broker_code'].str.lower() == broker_code.lower()].copy()
                if not account_holdings.empty:
                    logger.info(f"Found {len(account_holdings)} holdings with case-insensitive match for {broker_code}")
                else:
                    logger.warning(f"No holdings found for broker code {broker_code} (case-insensitive)")
            else:
                logger.info(f"Found {len(account_holdings)} holdings with exact match for {broker_code}")
            print(account_holdings)
            if not account_holdings.empty:
                # Sum quantities for same trading symbols
                account_holdings = account_holdings.drop_duplicates()
                account_holdings = account_holdings.groupby('trading_symbol')['quantity'].sum().reset_index()
                account_holdings = self.calculate_market_value(account_holdings)
                
                # Delete existing holdings for this account on this date
                logger.debug(f"Deleting existing holdings for account {account.single_account_id} on {file_date.date()}")
                stmt = AccountActualPortfolio.__table__.delete().where(
                    and_(
                        AccountActualPortfolio.owner_id == account.single_account_id,
                        AccountActualPortfolio.snapshot_date == file_date.date()
                    )
                )
                await db.execute(stmt)
                await db.commit()
                
                # Insert new holdings
                logger.debug(f"Inserting {len(account_holdings)} holdings for account {account.single_account_id}")
                for _, row in account_holdings.iterrows():
                    new_holding = AccountActualPortfolio(
                        owner_id=account.single_account_id,
                        owner_type='single',
                        snapshot_date=file_date.date(),
                        trading_symbol=row['trading_symbol'],
                        quantity=row['quantity'],
                        market_value=row['market_value']
                    )
                    db.add(new_holding)
            
            # Update account values - even if no holdings
            pf_value = account_holdings['market_value'].sum() if not account_holdings.empty else 0
            total_holdings = pf_value + cash_value
            logger.info(f"Updating account {account.single_account_id} with PF: {pf_value}, Cash: {cash_value}, Total: {total_holdings}")
            
            await db.execute(
                update(SingleAccount)
                .where(SingleAccount.single_account_id == account.single_account_id)
                .values(
                    pf_value=pf_value,
                    cash_value=cash_value,
                    total_holdings=total_holdings
                )
            )
            await db.commit()
            logger.info(f"Processed account {account.single_account_id} - PF: {pf_value}, Cash: {cash_value}, Total: {total_holdings}")
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error processing single account {broker_code}: {str(e)}")
            raise

    async def process_joint_account(self, db: AsyncSession, holdings_df: pd.DataFrame,
                                  joint_account: JointAccount, file_date: datetime,
                                  cash_df: pd.DataFrame) -> None:
        """Process holdings for a joint account."""
        try:
            # Get all single accounts in this joint account
            single_accounts = await self.joint_acc_service.get_linked_single_accounts(db, joint_account.joint_account_id)
            broker_codes = [acc['broker_code'].lower() for acc in single_accounts if acc['broker_code']]
            # Calculate total cash for all linked accounts
            total_cash = sum(self.get_cash_value(cash_df, code) for code in broker_codes)
            logger.debug(f"Total cash for joint account {joint_account.joint_account_id}: {total_cash}")
            # Aggregate holdings for all single accounts
            joint_holdings = holdings_df[holdings_df['broker_code'].isin(broker_codes)].copy()
            if not joint_holdings.empty:
                # Sum quantities for same trading symbols
                joint_holdings = joint_holdings.groupby('trading_symbol')['quantity'].sum().reset_index()
                joint_holdings = self.calculate_market_value(joint_holdings)
                
                # Delete existing records for this account and date
                logger.debug(f"Deleting existing holdings for joint account {joint_account.joint_account_id} on {file_date.date()}")
                stmt = AccountActualPortfolio.__table__.delete().where(
                    and_(
                        AccountActualPortfolio.owner_id == joint_account.joint_account_id,
                        AccountActualPortfolio.snapshot_date == file_date.date()
                    )
                )
                await db.execute(stmt)
                await db.commit()
                
                # Insert new holdings
                logger.debug(f"Inserting {len(joint_holdings)} holdings for joint account {joint_account.joint_account_id}")
                for _, row in joint_holdings.iterrows():
                    new_holding = AccountActualPortfolio(
                        owner_id=joint_account.joint_account_id,
                        owner_type='joint',
                        snapshot_date=file_date.date(),
                        trading_symbol=row['trading_symbol'],
                        quantity=row['quantity'],
                        market_value=row['market_value']
                    )
                    db.add(new_holding)
            
            # Update joint account values - even if no holdings
            pf_value = joint_holdings['market_value'].sum() if not joint_holdings.empty else 0
            total_holdings = pf_value + total_cash
            
            await db.execute(
                update(JointAccount)
                .where(JointAccount.joint_account_id == joint_account.joint_account_id)
                .values(
                    pf_value=pf_value,
                    cash_value=total_cash,
                    total_holdings=total_holdings
                )
            )
            await db.commit()
            logger.info(f"Processed joint account {joint_account.joint_account_id} - PF: {pf_value}, Cash: {total_cash}, Total: {total_holdings}")
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error processing joint account {joint_account.joint_account_id}: {str(e)}")
            raise

    async def process_outside_holdings(self, db: AsyncSession) -> None:
        """Main method to process outside holdings."""
        logger.info("Starting outside holdings processing")
        try:
            # Use a specific file instead of getting the latest
            file_info = self.get_latest_outside_holdings_file()
            if not file_info:
                logger.warning("No outside holdings file found - exiting")
                return
                
            file_path, file_date = file_info
            file_path = "/home/admin/Plus91Backoffice/Plus91_Backend/data/other_holdings/Outside_holdings_2025-03-25.xlsx"
            file_date = datetime.strptime("2025-03-25", "%Y-%m-%d")
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return
                
            logger.info(f"Using specified holdings file: {file_path} with date {file_date}")
            
            # Load Excel sheets
            logger.info(f"Loading data from {file_path}")
            holdings_df = pd.read_excel(file_path, sheet_name='pf')
            cash_df = pd.read_excel(file_path, sheet_name='cash')
            
            # Normalize broker codes in dataframes - convert to lowercase and strip spaces
            if 'broker_code' in holdings_df.columns:
                holdings_df['broker_code'] = holdings_df['broker_code'].astype(str).str.lower().str.strip()
                logger.info("Normalized broker codes in holdings dataframe")
            
            if 'broker_code' in cash_df.columns:
                cash_df['broker_code'] = cash_df['broker_code'].astype(str).str.lower().str.strip()
                logger.info("Normalized broker codes in cash dataframe")
            
            # Log the unique broker codes in the file to help with debugging
            unique_brokers_holdings = holdings_df['broker_code'].unique().tolist()
            unique_brokers_cash = cash_df['broker_code'].unique().tolist()
            logger.info(f"Unique broker codes in holdings file: {unique_brokers_holdings}")
            logger.info(f"Unique broker codes in cash file: {unique_brokers_cash}")
            
            # Load LTPs
            await self.load_ltps(db)
            
            # Process single accounts (excluding Zerodha and Keynote)
            result = await db.execute(
                select(SingleAccount)
                .join(Client, SingleAccount.single_account_id == Client.account_id)
                .join(Broker, Client.broker_id == Broker.broker_id)
                .where(~Broker.broker_name.in_(['zerodha', 'keynote']))
            )
            single_accounts = result.scalars().all()
            
            logger.info(f"Found {len(single_accounts)} single accounts to process (excluding Zerodha and Keynote)")
            
            processed_count = 0
            for account in single_accounts:
                print(account)
                # Get broker_code from Client table
                client_result = await db.execute(
                    select(Client.broker_code)
                    .where(Client.account_id == account.single_account_id)
                )
                broker_code = client_result.scalar_one_or_none()
                
                if broker_code:
                    # Normalize broker code to lowercase and strip whitespace
                    broker_code = broker_code.lower().strip()
                    print(broker_code)
                    logger.info(f"Processing single account {account.single_account_id} with normalized broker code '{broker_code}'")
                    await self.process_single_account(db, holdings_df, broker_code, file_date, cash_df)
                    processed_count += 1
                else:
                    logger.warning(f"No broker code found for single account {account.single_account_id}")
            
            logger.info(f"Processed {processed_count} out of {len(single_accounts)} single accounts")
            
            # Process joint accounts (excluding those with Zerodha/Keynote accounts)
            result = await db.execute(select(JointAccount))
            joint_accounts = result.scalars().all()
            
            logger.info(f"Found {len(joint_accounts)} joint accounts to check")
            
            joint_processed_count = 0
            for joint_account in joint_accounts:
                # Get linked single accounts and their brokers
                linked_accounts = await self.joint_acc_service.get_linked_single_accounts(db, joint_account.joint_account_id)
                
                logger.info(f"Joint account {joint_account.joint_account_id} has {len(linked_accounts)} linked single accounts")
                
                # Check if any linked account is from Zerodha/Keynote
                has_excluded_broker = False
                for acc in linked_accounts:
                    broker_result = await db.execute(
                        select(Broker.broker_name)
                        .join(Client, Broker.broker_id == Client.broker_id)
                        .where(Client.account_id == acc['account_id'])
                    )
                    broker_name = broker_result.scalar_one_or_none()
                    if broker_name and broker_name.lower() in ['zerodha', 'keynote']:
                        has_excluded_broker = True
                        logger.info(f"Skipping joint account {joint_account.joint_account_id} as it contains {broker_name} account")
                        break
                
                if not has_excluded_broker:
                    # Normalize broker codes for linked accounts
                    for acc in linked_accounts:
                        if acc.get('broker_code'):
                            acc['broker_code'] = acc['broker_code'].lower().strip()
                    
                    logger.info(f"Processing joint account {joint_account.joint_account_id}")
                    await self.process_joint_account(db, holdings_df, joint_account, file_date, cash_df)
                    joint_processed_count += 1
                else:
                    logger.info(f"Skipping joint account {joint_account.joint_account_id} as it contains Zerodha/Keynote accounts")
            
            logger.info(f"Processed {joint_processed_count} out of {len(joint_accounts)} joint accounts")
            logger.info("Outside holdings processing completed successfully")
            
        except Exception as e:
            logger.error(f"Error in outside holdings processing: {str(e)}")
            raise


if __name__ == "__main__":
    # Run the full outside holdings processing
    async def main():
        async with AsyncSessionLocal() as db:
            processor = OutsideAccProcessor()
            await processor.process_outside_holdings(db)
            
    asyncio.run(main())
