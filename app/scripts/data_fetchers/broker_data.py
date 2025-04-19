import json
import requests
from typing import List, Dict

class BrokerData:
    """Class containing static methods to interact with the Upstox API."""
    
    BASE_URL = "http://0.0.0.0:8001/api/v1/"
    
    @staticmethod
    def get_master_data() -> Dict:
        """
        Fetches the master data from the Upstox API.
        
        Returns:
            The JSON response from the API as a Python dictionary.
        
        Raises:
            Exception: If the API call fails, with the status code and error message.
        """
        url = f"{BrokerData.BASE_URL}master-data"
        headers = {"Content-Type": "application/json"}
        response = requests.get(url, params={"broker_type": "upstox"}, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Failed to get master data: {response.status_code} - {response.text}")
        return response.json()
    
    @staticmethod
    def get_ltp_quote(instruments: List[Dict[str, str]]) -> Dict:
        """
        Fetches the Last Traded Price (LTP) quote for the given instruments.
        
        Args:
            instruments: A list of dictionaries, each with 'exchange_token' and 'exchange' keys.
        
        Returns:
            The JSON response from the API as a Python dictionary.
        
        Raises:
            Exception: If the API call fails, with the status code and error message.
        """
        url = f"{BrokerData.BASE_URL}ltp-quote"
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=instruments, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Failed to get LTP quote: {response.status_code} - {response.text}")
        return response.json()
    
    @staticmethod
    def historical_data(broker_type: str, instrument: Dict) -> Dict:
        """
        Hits the /historical-data endpoint and returns the JSON response.

        Args:
            broker_type (str): The broker type (e.g., 'upstox').
            instrument (Dict): A dictionary with the instrument parameters. For example:
                {
                    "exchange": "NSE",
                    "exchange_token": "21195",
                    "instrument_type": "EQ",
                    "interval": "day",
                    "from_date": "2023-01-01",
                    "to_date": "2023-01-31"
                }

        Returns:
            Dict: The JSON response from the API.

        Raises:
            Exception: If the API call fails.
        """
        url = f"{BrokerData.BASE_URL}historical-data?broker_type={broker_type}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "instrument": json.dumps(instrument)
        }
        response = requests.post(url, json=instrument, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get historical data: {response.status_code} - {response.text}")

        
