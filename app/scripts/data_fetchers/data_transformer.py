import time
import boto3
from io import BytesIO
import pandas as pd
from datetime import datetime, timedelta
from app.scripts.data_fetchers.broker_data import BrokerData
from app.scripts.data_fetchers.portfolio_data import KeynoteApi, ZerodhaDataFetcher
from typing import Dict, Optional, Tuple
from app.logger import logger

broker_data = BrokerData()
master_data = broker_data.get_master_data()
upstox_master_df = pd.DataFrame(master_data["data"]) if master_data and "data" in master_data else pd.DataFrame()


class KeynoteDataTransformer:
    def __init__(self):
        """Initialize with KeynoteApi instance."""
        self.keynote_portfolio = KeynoteApi()

    async def transform_ledger_to_cashflow(
            self,
            broker_code: str,
            from_date: str,
            to_date: str
    ) -> Optional[Dict]:
        """Transform ledger data into cashflow format."""
        ledger_data = await self.keynote_portfolio.fetch_ledger(
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

        ledger_df_slice = ledger_df[ledger_df["type"].isin(["C"])]
        ledger_df_open_bal = ledger_df[ledger_df["type"].isin(["A"])]

        if ledger_df.empty:
            logger.warning(f"No cash transactions found in ledger data for {broker_code}.")
            return None

        try:
            cashflow_df = pd.DataFrame()
            cashflow_df["event_date"] = pd.to_datetime(ledger_df_slice["vrdt"]).dt.date
            cashflow_df["cashflow"] = ledger_df_slice["amtcr"].where(
                ledger_df_slice["amtcr"] > 0, -ledger_df_slice["amtdr"]
            ).astype(float)
            cashflow_df["tag"] = ""

            ledger_df['vrdt'] = pd.to_datetime(ledger_df['vrdt'])
            latest_row = ledger_df.sort_values('vrdt').iloc[-1]
            latest_balance = float(latest_row['runbal'])
            cashflow_df = cashflow_df.reset_index(drop=True)
            return cashflow_df.to_dict()
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
        holdings_data = await self.keynote_portfolio.fetch_holding(
            ucc=broker_code,
            for_date=for_date
        )
        if not holdings_data:
            logger.warning(f"Holdings for {broker_code} at date: {for_date} could not be found.")
        else:
            holdings_df = pd.DataFrame(holdings_data)
            if not holdings_df.empty and not for_date.startswith("2024-03"):
                try:
                    holdings_df["quantity"] = (holdings_df["holding"] / holdings_df["closerate"]).round(2)
                    holdings_df = holdings_df[["isincd", "quantity", "holding"]]
                    holdings_df = holdings_df.rename(columns={
                        "isincd": "isin",
                        "holding": "market_value"
                    })
                    slice_master_df = upstox_master_df[upstox_master_df["segment"].isin(["NSE_EQ", "BSE_EQ"])]
                    holdings_df = holdings_df.merge(slice_master_df[["isin", "trading_symbol"]], on="isin", how="left")
                    holdings_df["trading_symbol"] = holdings_df["trading_symbol"].fillna(holdings_df["isin"]).drop_duplicates()
                    holdings_df = holdings_df.groupby("trading_symbol")[["quantity", "market_value"]].sum().reset_index()
                    
                    # upstox_master_df_slice = upstox_master_df[
                    #     (upstox_master_df["exchange"].isin(["NSE", "BSE"])) &
                    #     (upstox_master_df["instrument_type"] == "EQ")
                    # ][["trading_symbol", "exchange", "exchange_token", "instrument_type"]]
                    
                    # upstox_master_df_slice_sorted = upstox_master_df_slice.sort_values(
                    #     by=["trading_symbol", "exchange"],
                    #     ascending=[True, True]
                    # )
                    # upstox_master_df_slice = upstox_master_df_slice_sorted.drop_duplicates(
                    #     subset="trading_symbol", keep="first"
                    # )
                    # mapping_data = upstox_master_df_slice[
                    #     upstox_master_df_slice["trading_symbol"].isin(list(holdings_df['trading_symbol']))
                    # ].reset_index()

                    # to_date = pd.to_datetime(for_date)
                    # from_date = to_date - timedelta(days=10)
                    # for index, data in mapping_data.iterrows():
                    #     try:
                    #         print(data)
                    #         hist_data = broker_data.historical_data(
                    #             instrument={
                    #                 "exchange": data['exchange'],
                    #                 "exchange_token": data['exchange_token'],
                    #                 "instrument_type": data['instrument_type'],
                    #                 "interval": "day",
                    #                 "from_date": str(from_date.date()),
                    #                 "to_date": str(to_date.date())
                    #             }
                    #         )
                    #         hist_df = pd.DataFrame(hist_data['data'])
                    #         closest_row = hist_df.iloc[(hist_df['datetime'] - pd.to_datetime(for_date)).abs().argsort()[0]]
                    #         print(closest_row)
                            
                    #         time.sleep(1)

                    #     except Exception as e:
                    #         print(f"Historical Data not found for {data}")

                    logger.info(f"Data fetched from API for {broker_code} on {for_date}")
                    return holdings_df.to_dict()
                except Exception as e:
                    logger.error(f"Error transforming API holdings for {broker_code}: {e}")

        logger.info(f"No data from API or transformation failed for {broker_code} on {for_date}. Falling back to S3...")

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
            cashflow_df["event_date"] = pd.to_datetime(cashflow_df["event_date"]).dt.date
            cashflow_df["cashflow"] = cashflow_df["cashflow"].astype(float)
            cashflow_df["tag"] = ""

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