import aiohttp
from app.logger import logger
from typing import Dict, Any, Optional, Tuple


class ReportServiceAPI:
    """Class to handle interactions with the Plus91 report service API."""
    
    def __init__(self, base_url: str):
        """Initialize with the API base URL."""
        self.base_url = base_url
        self.report_endpoint = f"{base_url}/reports/send-report"
    
    async def send_report_request(self, broker_code: str, pan_no: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Send a request to the report service API.
        
        Args:
            broker_code: The broker code provided by the user
            pan_no: The PAN number provided by the user
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Response data or error message (dict)
        """
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "broker_code": broker_code,
                    "pan_no": pan_no
                }
                logger.info(f"Sending request to {self.report_endpoint} with payload: {payload}")
                
                async with session.post(self.report_endpoint, json=payload) as response:
                    response_data = await response.json()
                    
                    if response.status == 200:
                        logger.info(f"API request successful: {response_data}")
                        return True, response_data
                    else:
                        logger.error(f"API request failed with status {response.status}: {response_data}")
                        error_detail = response_data.get("detail", "Unknown error")
                        return False, {"error": error_detail}
                        
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error: {str(e)}")
            return False, {"error": f"Connection error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error during API call: {str(e)}")
            return False, {"error": f"Unexpected error: {str(e)}"}
    
    async def verify_api_availability(self) -> bool:
        """
        Check if the API is available.
        
        Returns:
            Boolean indicating if the API is reachable
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/") as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"API availability check failed: {str(e)}")
            return False
