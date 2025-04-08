import requests
from typing import List, Dict

class BrokerData:
    """Class containing static methods to interact with the Upstox API."""
    
    BASE_URL = "http://13.127.138.190:8000/api/v1/upstox/"
    
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
        response = requests.get(url)
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
    def historical_data(instrument: Dict) -> Dict:
        """
        Fetches the Last Traded Price (LTP) quote for the given instruments.
        
        Args:
            instruments: A list of dictionaries, each with 'exchange_token' and 'exchange' keys.
        
        Returns:
            The JSON response from the API as a Python dictionary.
        
        Raises:
            Exception: If the API call fails, with the status code and error message.
        """
        url = f"{BrokerData.BASE_URL}historical-data"
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=instrument, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Failed to get historical data: {response.status_code} - {response.text}")
        return response.json()
    
