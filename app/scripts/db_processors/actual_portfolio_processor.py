import re
import sys
import boto3
import asyncio
import logging
import pandas as pd
from datetime import datetime
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.accounts.account_actual_portfolio import AccountActualPortfolio
from app.scripts.data_fetchers.data_transformer import (
    KeynoteDataTransformer, ZerodhaDataTransformer
)
from app.scripts.db_processors.helper_functions import (
    _generate_historical_month_ends, _get_existing_snapshot_dates
)
from typing import List, Dict
from app.models.accounts.account_actual_portfolio_exceptions import AccountActualPortfolioException
from app.logger import logger

class ActualPortfolioProcessor:
    def __init__(
            self,
            db: AsyncSession,
            keynote_transformer: KeynoteDataTransformer,
            zerodha_transformer: ZerodhaDataTransformer
    ):
        self.db = db
        self.s3 = boto3.client('s3')
        self.bucket_name = 'plus91backoffice'
        self.keynote_transformer = keynote_transformer
        self.zerodha_transformer = zerodha_transformer

    async def process_single_account_holdings(self, account: dict):
        """Process holdings data for a single account based on broker type."""
        try:
            broker_name = account.get('broker_name')
            account_id = account.get('account_id', 'unknown')
            if not broker_name:
                logger.warning(f"Broker name missing for account {account_id}. Skipping.")
                return

            if broker_name == "keynote":
                await self._process_keynote_holdings(account)
            elif broker_name == "zerodha":
                await self._process_zerodha_holdings(account)
            else:
                logger.warning(f"Unknown broker {broker_name} for account {account_id}. Skipping.")
        except Exception as e:
            logger.error(f"Error in process_single_account_holdings for account {account_id}: {e}")

    async def _fetch_exceptions(self, owner_id: str, owner_type: str) -> List[Dict]:
        """Fetch exceptions for a given owner_id and owner_type."""
        query = select(AccountActualPortfolioException).where(
            AccountActualPortfolioException.owner_id == owner_id,
            AccountActualPortfolioException.owner_type == owner_type
        )
        result = await self.db.execute(query)
        exceptions = result.scalars().all()
        return [{'trading_symbol': e.trading_symbol, 'quantity': e.quantity} for e in exceptions]

    def _adjust_portfolio(self, portfolio_dict: Dict, exceptions: List[Dict]) -> List[Dict]:
        """Adjust the portfolio data based on exceptions."""
        adjusted_portfolio = []
        exceptions_dict = {e['trading_symbol']: e['quantity'] for e in exceptions}

        for i in range(len(portfolio_dict['trading_symbol'])):
            symbol = portfolio_dict['trading_symbol'][i]
            quantity = portfolio_dict['quantity'][i]
            market_value = portfolio_dict['market_value'][i]

            if symbol in exceptions_dict:
                exclude_qty = exceptions_dict[symbol]
                if quantity <= exclude_qty:
                    continue
                else:
                    quantity -= exclude_qty
                    
                    market_value = (market_value / portfolio_dict['quantity'][i]) * quantity

            record = {
                "owner_id": portfolio_dict['owner_id'],
                "owner_type": portfolio_dict['owner_type'],
                "snapshot_date": portfolio_dict['snapshot_date'],
                "trading_symbol": symbol,
                "quantity": quantity,
                "market_value": market_value
            }
            adjusted_portfolio.append(record)

        return adjusted_portfolio

    async def _process_keynote_holdings(self, account: dict):
        """Process holdings data for a single Keynote account."""
        try:
            account_id = account.get('account_id')
            broker_code = account.get('broker_code')
            broker_name = account.get('broker_name', '').lower()
            
            # Set up temporary debug logger
            debug_logger = logging.getLogger('debug')
            
            debug_logger.info(f"\n{'='*50}")
            debug_logger.info(f"Processing Keynote holdings for {account_id} ({broker_code})")
            
            if not all([account_id, broker_code]):
                debug_logger.warning(f"Missing required account data for Keynote account: {account}")
                return

            prefix = f"PLUS91_PMS/ledgers_and_holdings/{broker_name}/single_accounts/{broker_code}/holdings/"
            debug_logger.info(f"Looking in S3 path: {prefix}")
            
            response = self.s3.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            if 'Contents' not in response:
                debug_logger.warning(f"No holdings files found in S3 for {broker_code}")
                return

            # Get all S3 dates
            s3_dates = []
            for obj in response['Contents']:
                filename = obj['Key'].split('/')[-1]
                if filename.endswith('.xlsx'):
                    match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
                    if match:
                        date_str = match.group(1)
                        s3_dates.append(datetime.strptime(date_str, '%Y-%m-%d').date())

            if not s3_dates:
                debug_logger.warning(f"No valid dates found in S3 holdings for {broker_code}")
                return

            debug_logger.info(f"\nAll S3 dates found: {sorted(s3_dates)}")
            
            existing_dates = await _get_existing_snapshot_dates(self.db, account_id)
            debug_logger.info(f"\nExisting dates in DB: {sorted(existing_dates)}")

            # Group dates by month
            s3_dates_by_month = {}
            existing_dates_by_month = {}

            # Group S3 dates
            for date in s3_dates:
                month_key = (date.year, date.month)
                if month_key not in s3_dates_by_month or date > s3_dates_by_month[month_key]:
                    s3_dates_by_month[month_key] = date

            # Group existing dates
            for date in existing_dates:
                month_key = (date.year, date.month)
                if month_key not in existing_dates_by_month or date > existing_dates_by_month[month_key]:
                    existing_dates_by_month[month_key] = date

            # Find months where S3 has newer data
            missing_historical_dates = []
            for month_key, s3_latest_date in s3_dates_by_month.items():
                existing_latest_date = existing_dates_by_month.get(month_key)
                if not existing_latest_date or s3_latest_date > existing_latest_date:
                    missing_historical_dates.append(s3_latest_date)

            missing_historical_dates.sort()
            debug_logger.info(f"\nFinal missing dates after comparison: {missing_historical_dates}")

            current_month_start = datetime.now().date().replace(day=1)
            debug_logger.info(f"\nCurrent month start: {current_month_start}")

            for date in missing_historical_dates:
                debug_logger.info(f"\nProcessing date: {date}")
                
                # Delete existing data for this specific date first
                await self.db.execute(
                    delete(AccountActualPortfolio)
                    .where(AccountActualPortfolio.owner_id == account_id)
                    .where(AccountActualPortfolio.owner_type == 'single')
                    .where(AccountActualPortfolio.snapshot_date == date)
                )
                await self.db.commit()
                debug_logger.info(f"Deleted existing portfolio entries for date: {date}")

                portfolio_dict, snapshot_date_str = await asyncio.wait_for(
                    self.keynote_transformer.transform_holdings_to_actual_portfolio(
                        broker_code=broker_code,
                        for_date=date.strftime("%Y-%m-%d")
                    ),
                    timeout=30
                )
                snapshot_date = datetime.strptime(snapshot_date_str, "%Y-%m-%d").date()
                if not portfolio_dict or not portfolio_dict.get("trading_symbol"):
                    logger.warning(f"No portfolio data for account {account_id} on {date}. Adding a null entry.")
                    null_portfolio = {
                        'owner_id': account_id,
                        'owner_type': 'single',
                        'snapshot_date': snapshot_date,
                        'trading_symbol': "place holder",
                        'quantity': 0,
                        'market_value': 0
                    }
                    self.db.add(AccountActualPortfolio(**null_portfolio))
                    await self.db.commit()
                    continue

                exceptions = await self._fetch_exceptions(account_id, 'single')

                adjusted_portfolio = self._adjust_portfolio({
                    'owner_id': account_id,
                    'owner_type': 'single',
                    'snapshot_date': snapshot_date,
                    'trading_symbol': portfolio_dict['trading_symbol'],
                    'quantity': portfolio_dict['quantity'],
                    'market_value': portfolio_dict['market_value']
                }, exceptions)

                for record in adjusted_portfolio:
                    self.db.add(AccountActualPortfolio(**record))
                debug_logger.info(f"Added adjusted portfolio records: {adjusted_portfolio}")
                await self.db.commit()
                debug_logger.info(f"Inserted adjusted portfolio records for account: {account_id}, date: {date}")
                logger.info(f"Inserted adjusted portfolio records for {account_id} on {date}")
        except asyncio.TimeoutError:
            logger.warning(f"Timeout processing holdings for Keynote account {account_id}. Skipping.")
            await self.db.rollback()
        except Exception as e:
            logger.error(f"Error processing holdings for Keynote account {account_id}: {e}")
            await self.db.rollback()

    async def _process_zerodha_holdings(self, account: dict):
        """Process holdings data for a single Zerodha account."""
        try:
            account_id = account.get('account_id')
            broker_code = account.get('broker_code')
            broker_name = account.get('broker_name', '').lower()

            logger.info(f"Processing Zerodha holdings for {account_id} ({broker_code})")
            
            if not all([account_id, broker_code]):
                logger.warning(f"Missing required account data for Zerodha account: {account}")
                return

            prefix = f"PLUS91_PMS/ledgers_and_holdings/{broker_name}/single_accounts/{broker_code}/holdings/"
            logger.info(f"Looking in S3 path: {prefix}")
            
            response = self.s3.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            if 'Contents' not in response:
                logger.warning(f"No holdings files found in S3 for {broker_code}")
                return

            s3_dates = []
            for obj in response['Contents']:
                filename = obj['Key'].split('/')[-1]
                if filename.endswith('.xlsx'):
                    match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
                    if match:
                        date_str = match.group(1)
                        s3_dates.append(datetime.strptime(date_str, '%Y-%m-%d').date())

            if not s3_dates:
                logger.warning(f"No valid dates found in S3 holdings for {broker_code}")
                return

            logger.info(f"All S3 dates found: {sorted(s3_dates)}")
            
            existing_dates = await _get_existing_snapshot_dates(self.db, account_id)
            logger.info(f"Existing dates in DB: {sorted(existing_dates)}")

            # Group dates by month
            s3_dates_by_month = {}
            existing_dates_by_month = {}

            # Group S3 dates
            for date in s3_dates:
                month_key = (date.year, date.month)
                if month_key not in s3_dates_by_month or date > s3_dates_by_month[month_key]:
                    s3_dates_by_month[month_key] = date

            # Group existing dates
            for date in existing_dates:
                month_key = (date.year, date.month)
                if month_key not in existing_dates_by_month or date > existing_dates_by_month[month_key]:
                    existing_dates_by_month[month_key] = date

            # Find months where S3 has newer data
            missing_historical_dates = []
            for month_key, s3_latest_date in s3_dates_by_month.items():
                existing_latest_date = existing_dates_by_month.get(month_key)
                if not existing_latest_date or s3_latest_date > existing_latest_date:
                    missing_historical_dates.append(s3_latest_date)

            missing_historical_dates.sort()
            logger.info(f"Final missing dates after comparison: {missing_historical_dates}")

            current_month_start = datetime.now().date().replace(day=1)
            logger.info(f"Current month start: {current_month_start}")

            # Delete current month data
            await self.db.execute(
                delete(AccountActualPortfolio)
                .where(AccountActualPortfolio.owner_id == account_id)
                .where(AccountActualPortfolio.owner_type == 'single')
                .where(AccountActualPortfolio.snapshot_date >= current_month_start)
            )
            await self.db.commit()
            logger.info(f"Deleted portfolio entries from {current_month_start} onwards")

            for date in missing_historical_dates:
                logger.info(f"Processing date: {date}")
                
                # Delete existing data for this specific date first
                await self.db.execute(
                    delete(AccountActualPortfolio)
                    .where(AccountActualPortfolio.owner_id == account_id)
                    .where(AccountActualPortfolio.owner_type == 'single')
                    .where(AccountActualPortfolio.snapshot_date == date)
                )
                await self.db.commit()
                logger.info(f"Deleted existing portfolio entries for date: {date}")

                portfolio_dict, snapshot_date_str = await asyncio.wait_for(
                    self.zerodha_transformer.transform_holdings_to_actual_portfolio(
                        broker_code=broker_code,
                        year=date.year,
                        month=date.month
                    ),
                    timeout=30
                )
                
                snapshot_date = datetime.strptime(snapshot_date_str, "%Y-%m-%d").date()
                if not portfolio_dict or not portfolio_dict.get("trading_symbol"):
                    logger.warning(f"No portfolio data for account {account_id} on {date}. Adding null entry.")
                    null_portfolio = {
                        'owner_id': account_id,
                        'owner_type': 'single',
                        'snapshot_date': snapshot_date,
                        'trading_symbol': "place holder",
                        'quantity': 0,
                        'market_value': 0
                    }
                    self.db.add(AccountActualPortfolio(**null_portfolio))
                    await self.db.commit()
                    continue

                exceptions = await self._fetch_exceptions(account_id, 'single')
                logger.info(f"Found {len(exceptions)} exceptions for account")

                adjusted_portfolio = self._adjust_portfolio({
                    'owner_id': account_id,
                    'owner_type': 'single',
                    'snapshot_date': snapshot_date,
                    'trading_symbol': portfolio_dict['trading_symbol'],
                    'quantity': portfolio_dict['quantity'],
                    'market_value': portfolio_dict['market_value']
                }, exceptions)

                for record in adjusted_portfolio:
                    self.db.add(AccountActualPortfolio(**record))
                await self.db.commit()
                logger.info(f"Successfully inserted {len(adjusted_portfolio)} holdings for {date}")
                
        except asyncio.TimeoutError:
            logger.warning(f"Timeout processing holdings for Zerodha account {account_id}")
            await self.db.rollback()
        except Exception as e:
            logger.error(f"Error processing holdings for Zerodha account {account_id}: {e}")
            await self.db.rollback()

    async def process_joint_accounts_holdings(self, joint_accounts: List[Dict]):
        """Process and update actual portfolios for joint accounts by aggregating from single accounts."""
        for joint_account in joint_accounts:
            joint_id = joint_account["joint_account_id"]
            single_accounts = joint_account["single_accounts"]
            single_ids = [acc["account_id"] for acc in single_accounts]

            if not single_ids:
                logger.warning(f"No single accounts for joint account {joint_id}")
                continue

            try:
                logger.info(f"Processing joint account: {joint_id}")
                
                # Get portfolio data from single accounts
                portfolio_query = (
                    select(AccountActualPortfolio)
                    .where(AccountActualPortfolio.owner_id.in_(single_ids))
                    .where(AccountActualPortfolio.owner_type == "single")
                )
                result = await self.db.execute(portfolio_query)
                portfolios = result.scalars().all()

                if not portfolios:
                    logger.warning(f"No portfolio data found for single accounts of joint account {joint_id}")
                    continue

                # Group by date
                portfolio_by_date = {}
                for p in portfolios:
                    date = p.snapshot_date
                    if date not in portfolio_by_date:
                        portfolio_by_date[date] = []
                    portfolio_by_date[date].append(p)

                # Delete existing portfolio records for the joint account
                await self.db.execute(
                    delete(AccountActualPortfolio)
                    .where(AccountActualPortfolio.owner_id == joint_id)
                    .where(AccountActualPortfolio.owner_type == "joint")
                )
                await self.db.commit()

                # Process each date's portfolio
                for snapshot_date, date_portfolios in portfolio_by_date.items():
                    # Aggregate holdings from single accounts
                    aggregated_portfolio = {}
                    for p in date_portfolios:
                        symbol = p.trading_symbol
                        if symbol in aggregated_portfolio:
                            aggregated_portfolio[symbol]["quantity"] += p.quantity
                            aggregated_portfolio[symbol]["market_value"] += p.market_value
                        else:
                            aggregated_portfolio[symbol] = {
                                "trading_symbol": symbol,
                                "quantity": p.quantity,
                                "market_value": p.market_value
                            }

                    # Get and apply exceptions
                    exceptions = await self._fetch_exceptions(joint_id, 'joint')
                    logger.info(f"Found {len(exceptions)} exceptions for joint account {joint_id}")

                    adjusted_portfolio = self._adjust_portfolio({
                        'owner_id': joint_id,
                        'owner_type': 'joint',
                        'snapshot_date': snapshot_date,
                        'trading_symbol': list(aggregated_portfolio.keys()),
                        'quantity': [data['quantity'] for data in aggregated_portfolio.values()],
                        'market_value': [data['market_value'] for data in aggregated_portfolio.values()]
                    }, exceptions)

                    # Insert aggregated records
                    for record in adjusted_portfolio:
                        self.db.add(AccountActualPortfolio(**record))
                    await self.db.commit()
                    logger.info(f"Successfully inserted {len(adjusted_portfolio)} holdings for {joint_id} on {snapshot_date}")

            except Exception as e:
                logger.error(f"Error processing portfolios for joint account {joint_id}: {e}")
                await self.db.rollback()

    async def calculate_pf_value(self, account_id: str, account_type: str) -> float:
        """Calculate the current portfolio value from the latest snapshot."""
        try:
            async with self.db as session:
                latest_date_query = select(func.max(AccountActualPortfolio.snapshot_date)).where(
                    AccountActualPortfolio.owner_id == account_id,
                    AccountActualPortfolio.owner_type == account_type
                )
                latest_date = (await session.execute(latest_date_query)).scalar()

                if latest_date:
                    sum_query = select(func.sum(AccountActualPortfolio.market_value)).where(
                        AccountActualPortfolio.owner_id == account_id,
                        AccountActualPortfolio.owner_type == account_type,
                        AccountActualPortfolio.snapshot_date == latest_date
                    )
                    result = await session.execute(sum_query)
                    return result.scalar()
                return 0.0
        except Exception as e:
            logger.error(f"Error calculating pf_value for {account_type} account {account_id}: {e}")
            return 0.0

    def get_fiscal_start(self, date_str: str) -> str:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        fiscal_year_start = datetime(date.year, 4, 1)
        if date < fiscal_year_start:
            fiscal_year_start = datetime(date.year - 1, 4, 1)
        
        return fiscal_year_start.strftime("%Y-%m-%d")

    async def initialize(self, accounts: List[Dict], joint_accounts: List[Dict]):
        """Orchestrate the processing of actual portfolios for single and joint accounts."""
        for account in accounts:
            await self.process_single_account_holdings(account)
        await self.process_joint_accounts_holdings(joint_accounts)