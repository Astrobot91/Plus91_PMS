import time
import boto3
from io import BytesIO
import pandas as pd
from datetime import datetime, timedelta
from app.scripts.data_fetchers.broker_data import BrokerData
from app.scripts.data_fetchers.portfolio_data import KeynoteDataProcessor, ZerodhaDataFetcher
from typing import Dict, Optional, Tuple
from app.logger import logger

broker_data = BrokerData()
master_data = broker_data.get_master_data()
upstox_master_df = pd.DataFrame(master_data["data"]) if master_data and "data" in master_data else pd.DataFrame()


class KeynoteDataTransformer:

    def __init__(self):
        """Initialize with KeynoteApi instance."""
        self.keynote_portfolio = KeynoteDataProcessor()
        self.fees = pd.read_excel("/home/admin/Plus91Backoffice/Plus91_Backend/data/cashflow_data/plus91_fees.xlsx")
        self.buybacks = pd.read_excel("/home/admin/Plus91Backoffice/Plus91_Backend/data/cashflow_data/plus91_buybacks.xlsx")
        self.share_transfers = pd.read_excel("/home/admin/Plus91Backoffice/Plus91_Backend/data/cashflow_data/plus91_share_transfers.xlsx")


    async def transform_ledger_to_cashflow(
            self,
            broker_code: str,
            from_date: str = None,
            to_date: str = None
    ) -> Optional[Dict]:
        """Transform ledger data into cashflow format."""
        try:
            ledger_data = self.keynote_portfolio.fetch_ledger(
                ucc=broker_code,
                from_date=from_date,
                to_date=to_date
            )
            if not ledger_data:
                logger.warning(f"Ledger data for {broker_code}, from: {from_date}, to: {to_date} was not found.")
                return None

            ledger_df = pd.DataFrame(ledger_data)
            if ledger_df.empty:
                logger.warning(f"Ledger data for {broker_code}, from: {from_date}, to: {to_date} is empty.")
                return None
            
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
            
            ledger_df = ledger_df[
                ledger_df['narr'].fillna('').str.startswith('AXIS BANK')
            ][["event_date", "debit", "credit"]]

            ledger_df['event_date'] = pd.to_datetime(ledger_df['event_date'], format='%d-%b-%Y', errors='coerce').dt.date
            ledger_df['cashflow'] = ledger_df['credit'].fillna(0) - ledger_df['debit'].fillna(0)
            ledger_df['tag'] = ""
            ledger_df = ledger_df[['event_date', 'cashflow', 'tag']].reset_index(drop=True)

            fees_data = self.fees[self.fees['broker_code'] == broker_code]
            if not fees_data.empty:
                fees_data['event_date'] = pd.to_datetime(fees_data['event_date'], format='%Y-%m-%d', errors='coerce').dt.date
                fees_data['tag'] = "fees"
                fees_data = fees_data[["event_date", "cashflow", "tag"]]
            else:
                fees_data = pd.DataFrame(columns=["event_date", "cashflow", "tag"])

            buybacks_data = self.buybacks[self.buybacks['broker_code'] == broker_code]
            if not buybacks_data.empty:
                buybacks_data['event_date'] = pd.to_datetime(buybacks_data['event_date'], format='%Y-%m-%d', errors='coerce').dt.date
                buybacks_data['cashflow'] = -buybacks_data['cashflow']
                buybacks_data['tag'] = "buyback"
                buybacks_data = buybacks_data[["event_date", "cashflow", "tag"]]
            else:
                buybacks_data = pd.DataFrame(columns=["event_date", "cashflow", "tag"])

            share_transfers_data = self.share_transfers[self.share_transfers['broker_code'] == broker_code]
            if not share_transfers_data.empty:
                share_transfers_data['event_date'] = pd.to_datetime(share_transfers_data['event_date'], format='%Y-%m-%d', errors='coerce').dt.date
                share_transfers_data['tag'] = "share transfer"
                share_transfers_data = share_transfers_data[["event_date", "cashflow", "tag"]]
            else:
                share_transfers_data = pd.DataFrame(columns=["event_date", "cashflow", "tag"])

            ledger_df = pd.concat(
                [ledger_df, fees_data, buybacks_data, share_transfers_data], ignore_index=True
            ).sort_values(by='event_date')
            return ledger_df.to_dict()
        except Exception as e:
            logger.error(f"Error transforming ledger to cashflow for {broker_code}: {e}")
            return None
        

    async def transform_holdings_to_actual_portfolio(
            self,
            broker_code: str,
            for_date: str
        ) -> Optional[Dict]:
        """
        Transform holdings data into actual portfolio format.
        First attempts to fetch data from the Keynote API, and if that fails,
        falls back to fetching the latest data from S3 for the same month and year.

        Args:
            broker_code (str): The UCC (e.g., 'MK100').
            for_date (str): The date in 'YYYY-MM-DD' format (e.g., '2023-07-12').

        Returns:
            Optional[Dict]: A dictionary with aggregated holdings data or None if no data is found.
        """
        bucket_name = 'plus91backoffice'
        prefix = f"PLUS91_PMS/ledgers_and_holdings/keynote/single_accounts/{broker_code}/holdings/"

        for_date_dt = datetime.strptime(for_date, "%Y-%m-%d")
        year = for_date_dt.year
        month = for_date_dt.month
        month_prefix = f"{year}-{month:02d}-"

        s3 = boto3.client('s3')
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        if 'Contents' not in response:
            logger.warning(f"No files found in S3 at {prefix}")
            return None

        files = [
            obj['Key'] for obj in response['Contents']
            if obj['Key'].endswith('.xlsx') and month_prefix in obj['Key']
        ]

        if not files:
            logger.warning(f"No files found for {year}-{month:02d} in S3 for {broker_code}")
            return None

        latest_file = max(files, key=lambda x: x.split('/')[-1].replace('.xlsx', ''))
        latest_date = latest_file.split('/')[-1].replace('.xlsx', '')
        logger.info(f"Found latest file: {latest_file} for {broker_code}")

        obj = s3.get_object(Bucket=bucket_name, Key=latest_file)
        file_content = obj['Body'].read()
        holdings_df = pd.read_excel(BytesIO(file_content))
        holdings_df = holdings_df.groupby("trading_symbol")[["quantity", "market_value"]].sum().reset_index()
        logger.info(f"Processed S3 data from {latest_date} for {broker_code}")
        return holdings_df.to_dict()


class ZerodhaDataTransformer:

    def __init__(self):
        """Initialize with ZerodhaDataFetcher instance."""
        self.zerodha_portfolio = ZerodhaDataFetcher()
        self.fees = pd.read_excel("/home/admin/Plus91Backoffice/Plus91_Backend/data/cashflow_data/plus91_fees.xlsx")
        self.buybacks = pd.read_excel("/home/admin/Plus91Backoffice/Plus91_Backend/data/cashflow_data/plus91_buybacks.xlsx")
        self.share_transfers = pd.read_excel("/home/admin/Plus91Backoffice/Plus91_Backend/data/cashflow_data/plus91_share_transfers.xlsx")


    async def transform_ledger_to_cashflow(
            self,
            broker_code: str
        ) -> Optional[Dict]:
        """Transform Zerodha ledger data into cashflow format."""
        ledger_data = self.zerodha_portfolio.get_ledger(
            broker_code=broker_code
        )
        if not ledger_data:
            logger.warning(f"Ledger data for {broker_code} could not be fetched.")
            return None

        ledger_df = pd.DataFrame(ledger_data)
        if ledger_df.empty:
            logger.warning(f"Ledger data for {broker_code} is empty.")
            return None

        ledger_df_slice = ledger_df[ledger_df['Voucher Type'].isin(['Bank Receipts', 'Bank Payments'])]
        if ledger_df.empty:
            logger.warning(f"No cash transactions found in ledger data for {broker_code}.")
            return None

        try:
            inflow_df = ledger_df_slice[["Posting Date", "Credit"]].rename(columns={"Posting Date": "event_date", "Credit": "cashflow"})
            inflow_df = inflow_df[inflow_df['cashflow'] != 0]

            outflow_df = ledger_df_slice[["Posting Date", "Debit"]].rename(columns={"Posting Date": "event_date", "Debit": "cashflow"})
            outflow_df['cashflow'] = -outflow_df['cashflow']
            outflow_df = outflow_df[outflow_df['cashflow'] != 0]

            cashflow_df = pd.concat([inflow_df, outflow_df], ignore_index=True)
            cashflow_df["event_date"] = pd.to_datetime(cashflow_df["event_date"], format='%Y-%m-%d', errors='coerce').dt.date
            cashflow_df["cashflow"] = cashflow_df["cashflow"].astype(float)
            cashflow_df["tag"] = ""

            fees_data = self.fees[self.fees['broker_code'] == broker_code]
            if not fees_data.empty:
                fees_data['event_date'] = pd.to_datetime(fees_data['event_date'], format='%Y-%m-%d', errors='coerce').dt.date
                fees_data['tag'] = "fees"
                fees_data = fees_data[["event_date", "cashflow", "tag"]]
            else:
                fees_data = pd.DataFrame(columns=["event_date", "cashflow", "tag"])

            buybacks_data = self.buybacks[self.buybacks['broker_code'] == broker_code]
            if not buybacks_data.empty:
                buybacks_data['event_date'] = pd.to_datetime(buybacks_data['event_date'], format='%Y-%m-%d', errors='coerce').dt.date
                buybacks_data['cashflow'] = -buybacks_data['cashflow']
                buybacks_data['tag'] = "buyback"
                buybacks_data = buybacks_data[["event_date", "cashflow", "tag"]]
            else:
                buybacks_data = pd.DataFrame(columns=["event_date", "cashflow", "tag"])

            share_transfers_data = self.share_transfers[self.share_transfers['broker_code'] == broker_code]
            if not share_transfers_data.empty:
                share_transfers_data['event_date'] = pd.to_datetime(share_transfers_data['event_date'], format='%Y-%m-%d', errors='coerce').dt.date
                share_transfers_data['tag'] = "share transfer"
                share_transfers_data = share_transfers_data[["event_date", "cashflow", "tag"]]
            else:
                share_transfers_data = pd.DataFrame(columns=["event_date", "cashflow", "tag"])

            cashflow_df = pd.concat(
                [cashflow_df, fees_data, buybacks_data, share_transfers_data], ignore_index=True
            ).sort_values(by='event_date')

            ledger_df['Posting Date'] = pd.to_datetime(ledger_df['Posting Date'])
            latest_row = ledger_df.sort_values('Posting Date').iloc[-1]
            latest_balance = float(latest_row['Net Balance'])
            cashflow_df = cashflow_df.reset_index(drop=True)
            return cashflow_df.to_dict()
        except Exception as e:
            logger.error(f"Error transforming Zerodha ledger to cashflow for {broker_code}: {e}")
            return None

    async def transform_holdings_to_actual_portfolio(
            self,
            broker_code: str,
            month: int,
            year: int
    ) -> Optional[Dict]:
        """Transform Zerodha holdings data into actual portfolio format."""
        holdings_data = self.zerodha_portfolio.get_holdings(
            broker_code=broker_code,
            month=month,
            year=year
        )
        if not holdings_data:
            logger.warning(f"Holdings for {broker_code} in {year}-{month:02d} could not be found.")
            return None

        holdings_df = pd.DataFrame(holdings_data)
        if holdings_df.empty:
            logger.warning(f"Holdings data for {broker_code} in {year}-{month:02d} is empty.")
            return None

        holdings_df = holdings_df[holdings_df["Unrealized P&L"] != 0]
        if holdings_df.empty:
            logger.warning(f"No holdings with unrealized P&L for {broker_code} in {year}-{month:02d}.")
            return None

        try:
            holdings_df["quantity"] = (
                    holdings_df['Quantity Available'] + holdings_df['Quantity Pledged (Margin)']
            )
            holdings_df["market_value"] = holdings_df['quantity'] * holdings_df['Previous Closing']
            holdings_df = holdings_df[["Symbol", "quantity", "market_value"]].rename(columns={"Symbol": "trading_symbol"})
            holdings_df = holdings_df.drop_duplicates().dropna(subset=["trading_symbol"])
            holdings_df["trading_symbol"] = holdings_df["trading_symbol"].str.split("-").str[0]
            holdings_df = holdings_df.groupby("trading_symbol")[["quantity", "market_value"]].sum().reset_index()
            return holdings_df.to_dict()
        except Exception as e:
            logger.error(f"Error transforming Zerodha holdings to portfolio for {broker_code}: {e}")
            return None