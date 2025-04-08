import sys
import asyncio
import logging
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
            acc_start_date = account.get('acc_start_date')
            fiscal_acc_start_date = self.get_fiscal_start(acc_start_date)
            broker_code = account.get('broker_code')
            if not all([account_id, acc_start_date, fiscal_acc_start_date, broker_code]):
                logger.warning(f"Missing required account data for Keynote account: {account}. Skipping.")
                return

            today = datetime.now().date()
            historical_dates = _generate_historical_month_ends(fiscal_acc_start_date, today)
            if not historical_dates:
                logger.warning(f"No historical dates generated for account {account_id}. Skipping.")
                return

            existing_dates = await _get_existing_snapshot_dates(self.db, account_id)
            missing_historical_dates = [date for date in historical_dates if date not in existing_dates]
            current_month_start = today.replace(day=1)
            await self.db.execute(
                delete(AccountActualPortfolio)
                .where(AccountActualPortfolio.owner_id == account_id)
                .where(AccountActualPortfolio.owner_type == 'single')
                .where(AccountActualPortfolio.snapshot_date >= current_month_start)
            )
            await self.db.commit()

            dates_to_fetch = missing_historical_dates + [today]
            for date in dates_to_fetch:
                portfolio_dict = await asyncio.wait_for(
                    self.keynote_transformer.transform_holdings_to_actual_portfolio(
                        broker_code=broker_code,
                        for_date=date.strftime("%Y-%m-%d")
                    ),
                    timeout=30
                )
                if not portfolio_dict or not portfolio_dict.get("trading_symbol"):
                    logger.warning(f"No portfolio data for account {account_id} on {date}. Adding a null entry.")
                    null_portfolio = {
                        'owner_id': account_id,
                        'owner_type': 'single',
                        'snapshot_date': date,
                        'trading_symbol': "place holder",
                        'quantity': 0,
                        'market_value': 0
                    }
                    null_portfolio
                    self.db.add(AccountActualPortfolio(**null_portfolio))
                    await self.db.commit()
                    continue

                exceptions = await self._fetch_exceptions(account_id, 'single')

                adjusted_portfolio = self._adjust_portfolio({
                    'owner_id': account_id,
                    'owner_type': 'single',
                    'snapshot_date': date,
                    'trading_symbol': portfolio_dict['trading_symbol'],
                    'quantity': portfolio_dict['quantity'],
                    'market_value': portfolio_dict['market_value']
                }, exceptions)

                for record in adjusted_portfolio:
                    self.db.add(AccountActualPortfolio(**record))
                await self.db.commit()
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
            acc_start_date = account.get('acc_start_date')
            broker_code = account.get('broker_code')
            if not all([account_id, acc_start_date, broker_code]):
                logger.warning(f"Missing required account data for Zerodha account: {account}. Skipping.")
                return

            today = datetime.now().date()
            historical_dates = _generate_historical_month_ends(acc_start_date, today)
            if not historical_dates:
                logger.warning(f"No historical dates generated for account {account_id}. Skipping.")
                return

            existing_dates = await _get_existing_snapshot_dates(self.db, account_id)
            missing_historical_dates = [date for date in historical_dates if date not in existing_dates]
            current_month_start = today.replace(day=1)
            await self.db.execute(
                delete(AccountActualPortfolio)
                .where(AccountActualPortfolio.owner_id == account_id)
                .where(AccountActualPortfolio.owner_type == 'single')
                .where(AccountActualPortfolio.snapshot_date >= current_month_start)
            )
            await self.db.commit()

            dates_to_fetch = missing_historical_dates + [today]
            for date in dates_to_fetch:
                portfolio_dict = await asyncio.wait_for(
                    self.zerodha_transformer.transform_holdings_to_actual_portfolio(
                        broker_code=broker_code,
                        year=date.year,
                        month=date.month
                    ),
                    timeout=30
                )
                if not portfolio_dict or not portfolio_dict.get("trading_symbol"):
                    logger.warning(f"No portfolio data for account {account_id} on {date}. Skipping date.")
                    null_portfolio = {
                        'owner_id': account_id,
                        'owner_type': 'single',
                        'snapshot_date': date,
                        'trading_symbol': "place holder",
                        'quantity': 0,
                        'market_value': 0
                    }
                    null_portfolio
                    self.db.add(AccountActualPortfolio(**null_portfolio))
                    await self.db.commit()
                    continue

                exceptions = await self._fetch_exceptions(account_id, 'single')

                adjusted_portfolio = self._adjust_portfolio({
                    'owner_id': account_id,
                    'owner_type': 'single',
                    'snapshot_date': date,
                    'trading_symbol': portfolio_dict['trading_symbol'],
                    'quantity': portfolio_dict['quantity'],
                    'market_value': portfolio_dict['market_value']
                }, exceptions)

                for record in adjusted_portfolio:
                    self.db.add(AccountActualPortfolio(**record))
                await self.db.commit()
                logger.info(f"Inserted adjusted portfolio records for {account_id} on {date}")
        except asyncio.TimeoutError:
            logger.warning(f"Timeout processing holdings for Zerodha account {account_id}. Skipping.")
            await self.db.rollback()
        except Exception as e:
            logger.error(f"Error processing holdings for Zerodha account {account_id}: {e}")
            await self.db.rollback()

    async def process_joint_accounts_holdings(self, joint_accounts: List[Dict]):
        """Process and update actual portfolios for joint accounts by aggregating from single accounts."""
        for joint_account in joint_accounts:
            joint_id = joint_account["joint_account_id"]
            single_accounts = joint_account["single_accounts"]

            if not single_accounts:
                logger.warning(f"No single accounts for joint account {joint_id}")
                continue

            try:
                acc_start_dates = [acc["acc_start_date"] for acc in single_accounts if acc["acc_start_date"]]
                if not acc_start_dates:
                    logger.warning(f"No valid acc_start_date for joint account {joint_id}")
                    continue
                earliest_start_date = min(acc_start_dates)

                today = datetime.now().date()
                historical_dates = _generate_historical_month_ends(earliest_start_date, today)
                if not historical_dates:
                    logger.warning(f"No historical dates generated for joint account {joint_id}")
                    continue

                existing_dates_query = (
                    select(AccountActualPortfolio.snapshot_date)
                    .where(AccountActualPortfolio.owner_id == joint_id)
                    .where(AccountActualPortfolio.owner_type == "joint")
                    .distinct()
                )
                result = await self.db.execute(existing_dates_query)
                existing_dates = set(row[0] for row in result.all())

                missing_historical_dates = [d for d in historical_dates if d not in existing_dates]
                dates_to_process = missing_historical_dates + [today]

                single_ids = [acc["account_id"] for acc in single_accounts]

                if today in dates_to_process:
                    current_month_start = today.replace(day=1)
                    delete_query = (
                        delete(AccountActualPortfolio)
                        .where(AccountActualPortfolio.owner_id == joint_id)
                        .where(AccountActualPortfolio.owner_type == "joint")
                        .where(AccountActualPortfolio.snapshot_date >= current_month_start)
                    )
                    await self.db.execute(delete_query)
                    await self.db.commit()

                for snapshot_date in dates_to_process:
                    portfolio_query = (
                        select(AccountActualPortfolio)
                        .where(AccountActualPortfolio.owner_id.in_(single_ids))
                        .where(AccountActualPortfolio.owner_type == "single")
                        .where(AccountActualPortfolio.snapshot_date == snapshot_date)
                    )
                    result = await self.db.execute(portfolio_query)
                    portfolios = result.scalars().all()

                    if not portfolios:
                        logger.warning(f"No portfolio data for joint account {joint_id} on {snapshot_date}")
                        continue

                    aggregated_portfolio = {}
                    for p in portfolios:
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
                    exceptions = await self._fetch_exceptions(joint_id, 'joint')

                    adjusted_portfolio = self._adjust_portfolio({
                        'owner_id': joint_id,
                        'owner_type': 'joint',
                        'snapshot_date': snapshot_date,
                        'trading_symbol': list(aggregated_portfolio.keys()),
                        'quantity': [data['quantity'] for data in aggregated_portfolio.values()],
                        'market_value': [data['market_value'] for data in aggregated_portfolio.values()]
                    }, exceptions)

                    for record in adjusted_portfolio:
                        self.db.add(AccountActualPortfolio(**record))

                    await self.db.commit()
                    logger.info(f"Inserted adjusted portfolio for joint account {joint_id} on {snapshot_date}")
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