import sys
import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import select, func
from app.database import AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.accounts.account_cashflow_details import AccountCashflow
from app.scripts.data_fetchers.data_transformer import KeynoteDataTransformer, ZerodhaDataTransformer
from app.scripts.data_fetchers.portfolio_data import ZerodhaDataFetcher, KeynoteDataProcessor
from app.scripts.db_processors.helper_functions import _generate_historical_month_ends
from typing import List, Dict
from app.logger import logger

keynote_portfolio = KeynoteDataProcessor()
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

            cashflow_dict = await self.keynote_transformer.transform_ledger_to_cashflow(
                broker_code=broker_code,
            )
            if not cashflow_dict or not cashflow_dict.get("event_date"):
                logger.warning(f"No cashflow data for Keynote account {account_id}. Skipping.")
                return

            # Delete existing cashflow records for the account
            await self.db.execute(
                AccountCashflow.__table__.delete().where(
                    AccountCashflow.owner_id == account_id,
                    AccountCashflow.owner_type == 'single'
                )
            )

            # Insert the new cashflow records
            cashflow_records = [
                {
                    "event_date": cashflow_dict["event_date"][i],
                    "cashflow": cashflow_dict["cashflow"][i],
                    "tag": cashflow_dict["tag"][i],
                    "owner_id": account_id,
                    "owner_type": "single"
                }
                for i in range(len(cashflow_dict["event_date"]))
            ]

            for record in cashflow_records:
                self.db.add(AccountCashflow(**record))
            await self.db.commit()
            logger.info(f"Overwritten with {len(cashflow_records)} cashflow records for account {account_id}")
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

            # Fetch the new cashflow data
            cashflow_dict = await self.zerodha_transformer.transform_ledger_to_cashflow(broker_code=broker_code)
            if not cashflow_dict or not cashflow_dict.get("event_date"):
                logger.warning(f"No cashflow data for Zerodha account {account_id}. Skipping.")
                return

            # Delete existing cashflow records for the account
            await self.db.execute(
                AccountCashflow.__table__.delete().where(
                    AccountCashflow.owner_id == account_id,
                    AccountCashflow.owner_type == 'single'
                )
            )

            # Insert the new cashflow records
            cashflow_records = [
                {
                    "event_date": cashflow_dict["event_date"][i],
                    "cashflow": cashflow_dict["cashflow"][i],
                    "tag": cashflow_dict["tag"][i],
                    "owner_id": account_id,
                    "owner_type": "single"
                }
                for i in range(len(cashflow_dict["event_date"]))
            ]

            for record in cashflow_records:
                self.db.add(AccountCashflow(**record))
            await self.db.commit()
            logger.info(f"Overwritten with {len(cashflow_records)} cashflow records for account {account_id}")
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

                # Delete existing cashflow records for the joint account
                await self.db.execute(
                    AccountCashflow.__table__.delete().where(
                        AccountCashflow.owner_id == joint_id,
                        AccountCashflow.owner_type == "joint"
                    )
                )

                # Insert the new aggregated cashflows
                for cf in aggregated_list:
                    new_record = AccountCashflow(
                        owner_id=joint_id,
                        owner_type="joint",
                        event_date=cf["event_date"],
                        cashflow=cf["cashflow"],
                        tag=cf["tag"]
                    )
                    self.db.add(new_record)

                await self.db.commit()
                logger.info(f"Overwritten with {len(aggregated_list)} cashflow records for joint account {joint_id}")
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
                ledger_data = keynote_portfolio.fetch_ledger(
                    ucc=broker_code
                )
                if not ledger_data:
                    logger.warning(f"No ledger data for Keynote account {account_id}")
                    return None
                ledger_df = pd.DataFrame(ledger_data)
                ledger_df.columns = [col.replace("_x000D_", "").replace("\n", "").strip() for col in ledger_df.columns]
                ledger_df = ledger_df.rename(columns={
                    'VoucherDate': 'event_date',
                    'AmountDebit': 'debit',
                    'AmountCredit': 'credit',
                    'RunningBalance': 'runbal',
                    'DrCr': 'type',
                    'EntryDetails': 'narr',
                    'Sett#': 'settl_no',
                    'Branch': 'branch',
                    'column_8': 'notes'
                })
                ledger_df = ledger_df[ledger_df["runbal"].notna()]
                ledger_df["event_date"] = pd.to_datetime(ledger_df["event_date"], format="%d-%b-%Y").dt.date
                ledger_df = ledger_df.dropna(subset=["event_date"]) 
                ledger_df["runbal"] = ledger_df["runbal"].astype(float)

                if ledger_df.empty:
                    logger.warning(f"Ledger data for Keynote account {account_id} is empty")
                    return None
                date_col = "event_date"
                balance_col = "runbal"
                balances = self.get_month_end_balances(ledger_df, date_col, balance_col, month_ends, broker_name)

            else:
                logger.warning(f"Unknown broker {broker_name} for account {account_id}")
                return None
            
            logger.info(f"Calculated {len(balances)} month-end cash balances for account {account_id}")
            return balances
        
        except Exception as e:
            logger.error(f"Error processing cash balances for account {account_id}: {e}")
            return None

    def get_month_end_balances(self, ledger_df: pd.DataFrame, date_col, balance_col, month_ends, broker_name):
        ledger_df[date_col] = pd.to_datetime(ledger_df[date_col])
        ledger_df = ledger_df.sort_values(by=date_col)
        month_ends = [pd.to_datetime(me) for me in month_ends]
        dates = ledger_df[date_col].values
        dates = [pd.Timestamp(date) for date in dates]
        balances = ledger_df[balance_col].values

        result = {}
        for monthend_date in month_ends:
            idx = np.searchsorted(dates, monthend_date, side='right')
            if idx > 0:
                balance = balances[idx - 1]
            else:
                balance = 0.0
            result[monthend_date.date()] = balance
        # shifted_result = {key + timedelta(days=1): value for key, value in result.items()}
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    async def main():
        async with AsyncSessionLocal() as db:
            keynote_transformer = KeynoteDataTransformer()
            zerodha_transformer = ZerodhaDataTransformer()

            # processor = CashflowProcessor(db, keynote_transformer, zerodha_transformer)

            # accounts = [
            #     {"account_id": "ACC_000303", "broker_name": "keynote", "acc_start_date": "2022-04-01", "broker_code": "MK100"},
            #     {"account_id": "ACC_000308", "broker_name": "zerodha", "acc_start_date": "2022-02-01", "broker_code": "BLQ476"}
            # ]

            # joint_accounts = [{
            #     'joint_account_id': 'JACC_000012',
            #     'single_accounts': [{
            #         'account_id': 'ACC_000312',
            #         'acc_start_date': '2022-05-01',
            #         'broker_code': 'MDK705',
            #         'broker_name': 'zerodha'
            #     }, {
            #         'account_id': 'ACC_000313',
            #         'acc_start_date': '2022-05-01',
            #         'broker_code': 'MM5525',
            #         'broker_name': 'zerodha'
            #     }]
            # }]

            # await processor.initialize(accounts, joint_accounts)

            # Example account and month-end dates
            # account = {
            #     "account_id": "ACC_000303",
            #     "broker_name": "keynote",
            #     "acc_start_date": "2022-04-01",
            #     "broker_code": "MK100"
            # }

            # month_ends = [
            #     datetime(2022, 4, 30),
            #     datetime(2022, 5, 31),
            #     datetime(2022, 6, 30),
            #     datetime(2022, 7, 31),
            #     datetime(2022, 8, 31),
            #     datetime(2022, 9, 30),
            #     datetime(2022, 10, 31),
            #     datetime(2022, 11, 30),
            #     datetime(2022, 12, 31),
            #     datetime(2023, 1, 31),
            #     datetime(2023, 2, 28),
            #     datetime(2023, 3, 31),
            #     datetime(2023, 4, 30),
            #     datetime(2023, 5, 31),
            #     datetime(2023, 6, 30),
            #     datetime(2023, 7, 31),
            #     datetime(2023, 8, 31),
            #     datetime(2023, 9, 30),
            #     datetime(2023, 10, 31),
            #     datetime(2023, 11, 30),
            #     datetime(2023, 12, 31),
            #     datetime(2024, 1, 31),
            #     datetime(2024, 2, 29),
            #     datetime(2024, 3, 31),
            #     datetime(2024, 4, 30),
            #     datetime(2024, 5, 31),
            #     datetime(2024, 6, 30),
            #     datetime(2024, 7, 31),
            #     datetime(2024, 8, 31),
            #     datetime(2024, 9, 30),
            #     datetime(2024, 10, 31),
            #     datetime(2024, 11, 30),
            #     datetime(2024, 12, 31),
            #     datetime(2025, 1, 31),
            #     datetime(2025, 2, 28),
            #     datetime(2025, 3, 31)
            # ]
            # balances = await processor.get_month_end_cash_balances(account, month_ends)
            # print("Month-end cash balances:", balances)

    asyncio.run(main())