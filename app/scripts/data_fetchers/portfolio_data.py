import os
import io
import boto3
import httpx
import asyncio
import datetime
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from app.scripts.data_fetchers.broker_data import BrokerData
from app.logger import logger
from typing import Dict


load_dotenv()
pd.set_option('future.no_silent_downcasting', True)

class ApiError(Exception):
    """Custom exception for API errors."""
    pass

class KeynoteApi:
    def __init__(self):
        """Initialize the API client with base URL, headers, and API key."""
        self.BASE_URL = "https://backoffice.wizzer.in/shrdbms/dotnet/api/stansoft/"
        self.HEADERS = {"Content-Type": "application/json"}
        self.API_KEY = os.getenv("SHAREPRO_WIZZER_API_KEY")

    async def fetch_holding(self, for_date: str, ucc: str) -> Dict:
        """
        Fetch holding data for a specific date and UCC.
        Returns a pandas DataFrame if successful, None otherwise.
        """
        url = self.BASE_URL + "GetDpHoldingData"
        payload = {
            "key": self.API_KEY,
            "ucc": ucc,
            "segments": "NSDL,CDSL,NFO,NSE,BSE",
            "date": datetime.strptime(for_date, "%Y-%m-%d").strftime("%d-%m-%Y")
        }
        try:
            data = await self._fetch_api_data(url, payload)
            return data.get("curdata", {})
        except ApiError as e:
            logger.error(f"Error fetching holding data: {e}")
            return None

    async def fetch_ledger(self, from_date: str, to_date: str, ucc: str) -> Dict:
        """
        Fetch ledger data between two dates for a UCC.
        Returns a pandas DataFrame if successful, None otherwise.
        """
        params = self._generate_ledger_params(from_date, to_date, ucc)
        all_transactions = []
        for p in params:
            url = self.BASE_URL + "ClientLedgerData"
            payload = {
                "key": self.API_KEY,
                "datefrom": p["datefrom"],
                "dateto": p["dateto"],
                "segments": "NSE,BSE,NFO",
                "ucc": p["ucc"],
                "accyear": p["accyear"]
            }
            try:
                data = await self._fetch_api_data(url, payload)
                if "curdata" in data:
                    all_transactions.extend(data["curdata"])
            except ApiError as e:
                logger.info(f"Error fetching ledger data for {p['datefrom']} to {p['dateto']}: {e}")
                continue
        if not all_transactions:
            return None
        
        all_transactions_df = pd.DataFrame(all_transactions)
        all_transactions_df["vrdt"] = pd.to_datetime(all_transactions_df["vrdt"]).dt.date
        return all_transactions_df.to_dict()
    
    def _generate_ledger_params(self, from_date: str, to_date: str, ucc: str):
        """
        Generate parameters for ledger API calls, splitting by financial years.
        Returns a list of parameter dictionaries.
        """
        from_date_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_date_dt = datetime.strptime(to_date, "%Y-%m-%d")
        params = []
        
        first_period_end = datetime(from_date_dt.year, 3, 31)
        if from_date_dt > first_period_end:
            first_period_end = datetime(from_date_dt.year + 1, 3, 31)
        if first_period_end > to_date_dt:
            first_period_end = to_date_dt
        
        params.append({
            "datefrom": from_date_dt.strftime("%d-%m-%Y"),
            "dateto": first_period_end.strftime("%d-%m-%Y"),
            "accyear": f"{from_date_dt.year % 100}{(from_date_dt.year + 1) % 100}",
            "ucc": ucc
        })
        
        while first_period_end < to_date_dt:
            next_period_start = datetime(first_period_end.year, 4, 1)
            next_period_end = datetime(first_period_end.year + 1, 3, 31)
            if next_period_end > to_date_dt:
                next_period_end = to_date_dt
            params.append({
                "datefrom": next_period_start.strftime("%d-%m-%Y"),
                "dateto": next_period_end.strftime("%d-%m-%Y"),
                "accyear": f"{next_period_start.year % 100}{(next_period_start.year + 1) % 100}",
                "ucc": ucc
            })
            first_period_end = next_period_end
        
        return params

    async def _fetch_api_data(self, url: str, payload: dict):
        """
        Helper function to fetch API data with retries and error handling.
        Returns a dictionary if successful, raises ApiError otherwise.
        """
        tries = 3
        for attempt in range(tries):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(url, headers=self.HEADERS, json=payload)
                    
                    if response.status_code != 200:
                        raise ApiError(f"Server error—status code {response.status_code}")
                    
                    content_type = response.headers.get('Content-Type', '').lower()
                    if 'application/json' not in content_type:
                        raise ApiError(f"Expected JSON, got {content_type or 'no content type'}")
                    
                    try:
                        data = response.json()
                    except ValueError:
                        raise ApiError("Response is not JSON")
                    
                    if not isinstance(data, dict):
                        raise ApiError(f"Expected dict, got {type(data).__name__}")
                    
                    return data
            
            except httpx.ReadTimeout:
                logger.info(f"Timeout on attempt {attempt + 1}/{tries}")
                if attempt < tries - 1:
                    await asyncio.sleep(5)
                else:
                    raise ApiError("Max retries reached, giving up")
            except httpx.HTTPStatusError as e:
                raise ApiError(f"HTTP error: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                raise ApiError(f"Unexpected error: {str(e)}")

class ZerodhaDataFetcher:
    def __init__(self, bucket_name="plus91backoffice", 
                 base_prefix="PLUS91_PMS/ledgers_and_holdings/zerodha/single_accounts/"):
        """Set up the S3 connection with your bucket and base prefix."""
        self.s3 = boto3.client('s3')
        self.bucket_name = bucket_name
        self.base_prefix = base_prefix.rstrip('/') + '/'

    def _get_s3_file_bytes(self, key):
        """Fetch an XLSX file from S3 and return its raw bytes."""
        full_key = self.base_prefix + key
        try:
            obj = self.s3.get_object(Bucket=self.bucket_name, Key=full_key)
            return obj['Body'].read()
        except Exception as e:
            logger.warning(f"Couldn’t grab {full_key}: {e}")
            return None

    def get_ledger(
            self, 
            broker_code: str, 
            as_dataframe=True
            ) -> Dict:
        """
        Fetch the ledger XLSX file for a broker_code from S3.
        Returns raw bytes if as_dataframe=False, or a pandas DataFrame if True.
        """
        key = f"{broker_code}/ledger/ledger-{broker_code}.xlsx"
        file_bytes = self._get_s3_file_bytes(key)
        if file_bytes is None:
            return None
        
        if not as_dataframe:
            return file_bytes
        
        df = pd.read_excel(io.BytesIO(file_bytes), header=None)
        new_column_names = {
                0: 'Index',
                1: 'Particulars',
                2: 'Posting Date',
                3: 'Cost Center',
                4: 'Voucher Type',
                5: 'Debit',
                6: 'Credit',
                7: 'Net Balance'
            }
        df = df.rename(columns=new_column_names)
        df = df.fillna('blank')
        df = df[df["Net Balance"] != "blank"].reset_index(drop=True).drop(columns=["Index"], index=0).reset_index(drop=True)
        df["Posting Date"] = pd.to_datetime(df["Posting Date"].replace("blank", pd.NaT), errors="coerce")
        df["Credit"] = pd.to_numeric(df["Credit"].replace("blank", 0), errors='coerce')
        df["Debit"] = pd.to_numeric(df["Debit"].replace("blank", 0), errors='coerce')
        df["Net Balance"] = pd.to_numeric(df["Net Balance"].replace("blank", 0), errors="coerce")
        return df.to_dict()

    def get_holdings(
            self,
            year: int,
            month: int,
            broker_code: str,
            as_dataframe=True
            ) -> Dict:
        """
        Fetch the latest holdings XLSX file for a given month and year for a broker_code.
        Returns raw bytes if as_dataframe=False, or a list of pandas DataFrames if True.
        """
        target_year_month = f"{year}-{month:02d}"
        prefix = f"{broker_code}/holdings/"
        
        response = self.s3.list_objects_v2(Bucket=self.bucket_name, 
                                          Prefix=self.base_prefix + prefix)
        if 'Contents' not in response:
            logger.warning(f"No holdings files found for {broker_code} under {self.base_prefix + prefix}!")
            return None

        holdings_files = []
        for obj in response['Contents']:
            try:
                file_date_str = obj['Key'].split('/')[-1].replace('.xlsx', '')
                file_date = datetime.strptime(file_date_str, "%Y-%m-%d")
                if file_date.strftime("%Y-%m") == target_year_month:
                    holdings_files.append((obj['Key'].replace(self.base_prefix, ''), file_date))
            except ValueError:
                logger.info(f"Skipping odd file name: {obj['Key']}")

        if not holdings_files:
            logger.warning(f"No holdings files for {target_year_month} under {broker_code}!")
            return None

        latest_file = max(holdings_files, key=lambda x: x[1])
        file_bytes = self._get_s3_file_bytes(latest_file[0])
        if file_bytes is None:
            return None
        
        if not as_dataframe:
            return file_bytes

        df = pd.read_excel(io.BytesIO(file_bytes), header=None)
        new_column_names = {
            1: 'Symbol',
            2: 'ISIN',
            3: 'Sector',
            4: 'Quantity Available',
            5: 'Quantity Discrepant',
            6: 'Quantity Long Term',
            7: 'Quantity Pledged (Margin)',
            8: 'Quantity Pledged (Loan)',
            9: 'Average Price',
            10: 'Previous Closing',
            11: 'Unrealized P&L',
            12: 'Unrealized P&L Pct'
        }
        df = df.rename(columns=new_column_names).drop(columns=0).fillna("blank")
        df = df[df["Unrealized P&L Pct"] != "blank"].reset_index(drop=True).drop(index=0).reset_index(drop=True)
        return df.to_dict()



if __name__ == "__main__":
    fetcher = ZerodhaDataFetcher()


    keynote = KeynoteApi()


    holdingsexample = asyncio.run(keynote.fetch_holding(for_date="2023-01-31", ucc="SG102"))
    df = pd.DataFrame(holdingsexample)
    print(df)

    # ledgerexample = asyncio.run(keynote.fetch_ledger(from_date="2022-11-30", to_date="2025-03-19", ucc="SG102"))
    # ledger_df = pd.DataFrame(ledgerexample)
    # ledger_df.to_csv("LEDGER_SG102.csv")
