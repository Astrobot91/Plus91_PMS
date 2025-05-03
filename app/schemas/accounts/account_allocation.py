from pydantic import BaseModel, Field, create_model, root_validator
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

class BaseAccountAllocation(BaseModel):
    account_id: str = Field(..., description="Account ID (single or joint)")
    account_name: str = Field(..., description="Name of the account")
    account_type: str = Field(..., description="Type of account (single/joint)")
    portfolio_name: Optional[str] = Field(None, description="Portfolio template name or Custom Portfolio")
    bracket_name: Optional[str] = Field(None, description="Name of the bracket")
    total_allocation: float = Field(..., description="Sum of all basket allocations")
    broker_name: Optional[str] = Field(None, description="Name of the broker")
    broker_code: Optional[str] = Field(None, description="Broker code")
    last_updated: Optional[str] = Field(None, description="Last updated timestamp for allocations")

class BaseAccountUpdate(BaseModel):
    account_id: str = Field(..., description="Account ID to update")
    account_type: str = Field(..., description="Account type (single/joint)")

def create_allocation_model(basket_names: List[str]):
    """Dynamically create a model with basket allocation fields."""
    field_definitions = {
        basket_name: (float, Field(..., description=f"Allocation percentage for {basket_name}"))
        for basket_name in basket_names
    }
    return create_model(
        'AccountAllocationResponse',
        __base__=BaseAccountAllocation,
        **field_definitions
    )

def create_update_model(basket_names: List[str]):
    """Dynamically create an update model with basket allocation fields."""
    field_definitions = {
        basket_name: (float, Field(..., description=f"Allocation percentage for {basket_name}"))
        for basket_name in basket_names
    }
    return create_model(
        'AccountAllocationUpdate',
        __base__=BaseAccountUpdate,
        **field_definitions
    )

class UpdateAllocationsResponse(BaseModel):
    total_accounts: int = Field(..., description="Total number of accounts in the update request")
    processed: int = Field(..., description="Number of accounts successfully processed")
    results: List[Dict[str, Any]] = Field(..., description="Results for each account update")

# Google Sheets specific models

class BasketInfo(BaseModel):
    id: int = Field(..., description="Basket ID")
    name: str = Field(..., description="Basket name")
    is_leveraged: bool = Field(..., description="Whether the basket is marked as leveraged")

class AccountAllocationsSheetResponse(BaseModel):
    data: List[List[Any]] = Field(..., description="Formatted data for Google Sheets")
    baskets: List[BasketInfo] = Field(..., description="Information about all baskets")

class GoogleSheetUpdateRequest(BaseModel):
    """
    Request model for Google Sheets updates.
    Supports both the old array format with 'sheet_data' field 
    and the new JSON object format with 'data' field.
    """
    sheet_data: Optional[List[List[Any]]] = Field(None, description="Sheet data from Google Sheets (old format)")
    data: Optional[List[Dict[str, Any]]] = Field(None, description="Account allocation data as array of objects (new format)")

    class Config:
        # This enables accepting either sheet_data or data field
        validate_assignment = True

    @root_validator(pre=True)
    def check_data_format(cls, values):
        """Validate that at least one of sheet_data or data is provided."""
        if not values.get('sheet_data') and not values.get('data'):
            raise ValueError("Either 'sheet_data' or 'data' must be provided")
        return values

class GoogleSheetUpdateResponse(BaseModel):
    total_rows: int = Field(..., description="Total number of data rows in the sheet")
    processed: int = Field(..., description="Number of rows successfully processed")
    results: List[Dict[str, Any]] = Field(..., description="Results for each account update")
    errors: List[str] = Field([], description="Any errors that occurred during processing")