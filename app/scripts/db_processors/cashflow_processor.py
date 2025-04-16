import sys
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.accounts.account_cashflow_details import AccountCashflow
from app.scripts.data_fetchers.data_transformer import KeynoteDataTransformer, ZerodhaDataTransformer
from app.scripts.data_fetchers.portfolio_data import ZerodhaDataFetcher, KeynoteApi
from app.scripts.db_processors.helper_functions import _generate_historical_month_ends
from typing import List, Dict
from app.logger import logger

keynote_portfolio = KeynoteApi()
zerodha_portfolio = ZerodhaDataFetcher()

class CashflowProcessor:
    def __init__(
            self, 
            db: AsyncSession, 
            keynote_transformer: KeynoteDataTransformer, 
            zerodha_transformer: ZerodhaDataTransformer
        ):
        self.db = db
        self.keynote_transformer = keynote_transformer
        self.zerodha_transformer = zerodha_transformer

    async def process_single_account_ledger(self, account: dict):
        """Process ledger data for a single account based on broker type."""
        try:
            broker_name = account.get('broker_name')
            account_id = account.get('account_id', 'unknown')
            if not broker_name:
                logger.warning(f"Broker name missing for account {account_id}")
                return

            if broker_name == "keynote":
                await self._process_keynote_ledger(account)
            elif broker_name == "zerodha":
                await self._process_zerodha_ledger(account)
            else:
                logger.warning(f"Unknown broker {broker_name} for account {account_id}. Skipping.")
        except Exception as e:
            logger.error(f"Error in process_single_account_ledger for account {account_id}: {e}")

    async def _process_keynote_ledger(self, account: dict):
        """Process ledger data for a single Keynote account."""
        try:
            account_id = account.get('account_id')
            acc_start_date = account.get('acc_start_date')
            fiscal_acc_start_date = self.get_fiscal_start(acc_start_date)
            broker_code = account.get('broker_code')
            if not all([account_id, acc_start_date, fiscal_acc_start_date, broker_code]):
                logger.warning(f"Missing required account data for Keynote account: {account}")
                return

            today = datetime.now().date()
            latest_event = await self.db.execute(
                select(func.max(AccountCashflow.event_date))
                .where(AccountCashflow.owner_id == account_id)
                .where(AccountCashflow.owner_type == 'single')
            )
            latest_event_date = latest_event.scalar()

            cashflow_dict = await self.keynote_transformer.transform_ledger_to_cashflow(
                broker_code=broker_code,
                from_date=fiscal_acc_start_date,
                to_date=today.strftime("%Y-%m-%d")
            )
            if not cashflow_dict or not cashflow_dict.get("event_date"):
                logger.warning(f"No cashflow data for Keynote account {account_id}. Skipping.")
                return

            cashflow_records = [
                {
                    "event_date": cashflow_dict["event_date"][i],
                    "cashflow": cashflow_dict["cashflow"][i],
                    "tag": cashflow_dict["tag"][i],
                    "owner_id": account_id,
                    "owner_type": "single"
                }
                for i in range(len(cashflow_dict["event_date"]))
                if latest_event_date is None or cashflow_dict["event_date"][i] > latest_event_date
            ]

            for record in cashflow_records:
                self.db.add(AccountCashflow(**record))
            await self.db.commit()
            logger.info(f"Inserted {len(cashflow_records)} cashflow records for account {account_id}")
        except Exception as e:
            logger.error(f"Error processing ledger for Keynote account {account_id}: {e}", exc_info=True)
            await self.db.rollback()

    async def _process_zerodha_ledger(self, account: dict):
        """Process ledger data for a single Zerodha account."""
        try:
            account_id = account.get('account_id')
            acc_start_date = account.get('acc_start_date')
            broker_code = account.get('broker_code')
            if not all([account_id, acc_start_date, broker_code]):
                logger.warning(f"Missing required account data for Zerodha account: {account}")
                return

            today = datetime.now().date()
            latest_event = await self.db.execute(
                select(func.max(AccountCashflow.event_date))
                .where(AccountCashflow.owner_id == account_id)
                .where(AccountCashflow.owner_type == 'single')
            )
            latest_event_date = latest_event.scalar()
            
            cashflow_dict = await self.zerodha_transformer.transform_ledger_to_cashflow(broker_code=broker_code)
            if not cashflow_dict or not cashflow_dict.get("event_date"):
                logger.warning(f"No cashflow data for Zerodha account {account_id}. Skipping.")
                return

            cashflow_records = [
                {
                    "event_date": cashflow_dict["event_date"][i],
                    "cashflow": cashflow_dict["cashflow"][i],
                    "tag": cashflow_dict["tag"][i],
                    "owner_id": account_id,
                    "owner_type": "single"
                }
                for i in range(len(cashflow_dict["event_date"]))
                if latest_event_date is None or cashflow_dict["event_date"][i] > latest_event_date
            ]

            for record in cashflow_records:
                self.db.add(AccountCashflow(**record))
            await self.db.commit()
            logger.info(f"Inserted {len(cashflow_records)} cashflow records for account {account_id}")
        except Exception as e:
            logger.error(f"Error processing ledger for Zerodha account {account_id}: {e}", exc_info=True)
            await self.db.rollback()

    async def process_joint_accounts_ledger(self, joint_accounts: List[Dict]):
        """Process and update cashflows for joint accounts by aggregating from single accounts."""
        for joint_account in joint_accounts:
            joint_id = joint_account["joint_account_id"]
            single_accounts = joint_account["single_accounts"]
            single_ids = [acc["account_id"] for acc in single_accounts]

            if not single_ids:
                logger.warning(f"No single accounts for joint account {joint_id}")
                continue

            try:
                cashflow_query = (
                    select(AccountCashflow)
                    .where(AccountCashflow.owner_id.in_(single_ids))
                    .where(AccountCashflow.owner_type == "single")
                )
                result = await self.db.execute(cashflow_query)
                cashflows = result.scalars().all()

                if not cashflows:
                    logger.info(f"No cashflows found for single accounts of joint account {joint_id}")
                    continue

                aggregated_cashflows = {}
                for cf in cashflows:
                    date = cf.event_date
                    if date in aggregated_cashflows:
                        aggregated_cashflows[date]["cashflow"] += cf.cashflow                            
                    else:
                        aggregated_cashflows[date] = {
                            "event_date": date,
                            "cashflow": cf.cashflow,
                            "tag": ""
                        }
                    
                aggregated_list = list(aggregated_cashflows.values())
                aggregated_list.sort(key=lambda x: x["event_date"])
                latest_event_query = (
                    select(func.max(AccountCashflow.event_date))
                    .where(AccountCashflow.owner_id == joint_id)
                    .where(AccountCashflow.owner_type == "joint")
                )
                result = await self.db.execute(latest_event_query)
                latest_event_date = result.scalar()

                new_cashflows = (
                    [cf for cf in aggregated_list if cf["event_date"] > latest_event_date]
                    if latest_event_date
                    else aggregated_list
                )

                if not new_cashflows:
                    logger.info(f"No new cashflows to insert for joint account {joint_id}")
                    continue

                for cf in new_cashflows:
                    new_record = AccountCashflow(
                        owner_id=joint_id,
                        owner_type="joint",
                        event_date=cf["event_date"],
                        cashflow=cf["cashflow"],
                        tag=cf["tag"]
                    )
                    self.db.add(new_record)

                await self.db.commit()
                logger.info(f"Inserted {len(new_cashflows)} cashflow records for joint account {joint_id}")
            except Exception as e:
                logger.error(f"Error processing cashflows for joint account {joint_id}: {e}")
                await self.db.rollback()

    async def get_month_end_cash_balances(self, account: dict, month_ends: list):
        """Retrieve month-end cash balances for a given account from acc_start_date to today."""
        broker_name = account.get('broker_name')
        account_id = account.get('account_id')
        acc_start_date = account.get('acc_start_date')
        broker_code = account.get('broker_code')
        
        if not all([broker_name, account_id, acc_start_date, broker_code]):
            logger.warning(f"Missing required account data for {broker_name} account: {account}")
            return None
        
        today = datetime.now().date()
        # month_ends = _generate_historical_month_ends(acc_start_date, today)
        
        month_ends_shifted = []
        for month_end in month_ends:
            new_month_end = month_end - timedelta(days=1)
            month_ends_shifted.append(new_month_end)

        if not month_ends:
            logger.warning(f"No month-end dates generated for account {account_id}")
            return None
        
        try:
            balances = []
            if broker_name == "zerodha":
                ledger_data = zerodha_portfolio.get_ledger(broker_code=broker_code)
                if not ledger_data:
                    logger.warning(f"No ledger data for Zerodha account {account_id}")
                    return {}
                ledger_df = pd.DataFrame(ledger_data)
                if ledger_df.empty:
                    logger.warning(f"Ledger data for Zerodha account {account_id} is empty")
                    return {}
                date_col = "Posting Date"
                balance_col = "Net Balance"
                balances = self.get_month_end_balances(ledger_df, date_col, balance_col, month_ends, broker_name)
            
            elif broker_name == "keynote":
                from_date = acc_start_date
                to_date = today.strftime("%Y-%m-%d")
                ledger_data = await keynote_portfolio.fetch_ledger(
                    from_date=from_date,
                    to_date=to_date,
                    ucc=broker_code
                )
                if not ledger_data:
                    logger.warning(f"No ledger data for Keynote account {account_id}")
                    return None
                ledger_df = pd.DataFrame(ledger_data)
                if ledger_df.empty:
                    logger.warning(f"Ledger data for Keynote account {account_id} is empty")
                    return None
                date_col = "vrdt"
                balance_col = "runbal"
                balances = self.get_month_end_balances(ledger_df, date_col, balance_col, month_ends_shifted, broker_name)

            else:
                logger.warning(f"Unknown broker {broker_name} for account {account_id}")
                return None
            
            logger.info(f"Calculated {len(balances)} month-end cash balances for account {account_id}")
            return balances
        
        except Exception as e:
            logger.error(f"Error processing cash balances for account {account_id}: {e}")
            return None

    def get_month_end_balances(self, ledger_df: pd.DataFrame, date_col, balance_col, month_ends, broker_name):
        print("LEDGER_DF: ", ledger_df)
        ledger_df.to_csv("MK100_LEDGER.csv")
        ledger_df[date_col] = pd.to_datetime(ledger_df[date_col])
        ledger_df = ledger_df.sort_values(by=date_col)
        month_ends = [pd.to_datetime(me) for me in month_ends]
        print(f"MONTHENDS: {month_ends}")
        dates = ledger_df[date_col].values
        dates = [pd.Timestamp(date) for date in dates]
        balances = ledger_df[balance_col].values
        print(balances)

        result = {}
        for monthend_date in month_ends:
            idx = np.searchsorted(dates, monthend_date, side='right')
            if idx > 0:
                balance = balances[idx - 1]
            else:
                balance = 0.0
            result[monthend_date.date()] = balance

        shifted_result = {key + timedelta(days=1): value for key, value in result.items()}
        
        if broker_name.lower() == 'keynote':
            return shifted_result
        else:
            return result

    async def calculate_invested_amt(self, account_id: str, account_type: str) -> float:
        """Calculate the total invested amount as the sum of all cashflows."""
        try:
            sum_query = select(func.sum(AccountCashflow.cashflow)).where(
                AccountCashflow.owner_id == account_id,
                AccountCashflow.owner_type == account_type
            )
            result = await self.db.execute(sum_query)
            invested_amt = result.scalar() or 0.0
            return invested_amt
        except Exception as e:
            logger.error(f"Error calculating invested_amt for {account_type} account {account_id}: {e}")
            return 0.0

    async def calculate_cash_value(self, account: dict, month_ends: list) -> float:
        """Calculate the latest cash balance for the account."""
        try:
            balances = await self.get_month_end_cash_balances(account, month_ends)
            print("BALANCES: ", balances)
            if balances:
                latest_date = max(balances.keys())
                return balances[latest_date]
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating cash_value for account {account['account_id']}: {e}")
            return 0.0

    def get_fiscal_start(self, date_str: str) -> str:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        fiscal_year_start = datetime(date.year, 4, 1)
        if date < fiscal_year_start:
            fiscal_year_start = datetime(date.year - 1, 4, 1)
        
        return fiscal_year_start.strftime("%Y-%m-%d")

    async def initialize(self, accounts: List[Dict], joint_accounts: List[Dict]):
        """Orchestrate the processing of cashflows for single and joint accounts."""
        for account in accounts:
            await self.process_single_account_ledger(account)
        await self.process_joint_accounts_ledger(joint_accounts)
