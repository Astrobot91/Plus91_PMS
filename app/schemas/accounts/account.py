import math
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from datetime import datetime


def sanitize_float(value):
    """
    Sanitize a float value by replacing NaN or Infinity with None.
    
    Args:
        value: The value to sanitize (could be None, float, or other types).
    
    Returns:
        None if the value is NaN or Infinity, otherwise the original value.
    """
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value

class ViewAccount(BaseModel):
    account_type: str = Field(..., description="Type of account: 'single' or 'joint'")
    account_id: str = Field(..., description="Unique account ID (single_account_id or joint_account_id)")
    account_name: str = Field(..., description="Name of the single or joint account")

    bracket_name: Optional[str] = Field(None, description="Friendly name of the associated bracket")
    portfolio_name: Optional[str] = Field(None, description="Friendly name of the associated portfolio template")

    pf_value: Optional[float] = Field(None, description="Portfolio value")
    cash_value: Optional[float] = Field(None, description="Current cash balance in the account")
    total_holdings: Optional[float] = Field(None, description="Total worth of all holdings in the account")
    invested_amt: Optional[float] = Field(None, description="Total invested amount so far")

    total_twrr: Optional[float] = Field(None, description="Time-weighted rate of return (overall)")
    current_yr_twrr: Optional[float] = Field(None, description="Current year TWRR (time-weighted rate of return)")
    cagr: Optional[float] = Field(None, description="Compound annual growth rate")

    created_at: Optional[str] = Field(None, description="Timestamp of account creation, in ISO format")
    latest_snapshot_date: Optional[str] = Field(None, description="Latest date from account_actual_portfolio, in ISO format")

    class Config:
        json_encoders = {
            float: sanitize_float
        }

class ViewAccountsResponse(BaseModel):
    status: str = Field("success", description="Response status, e.g., 'success' or 'error'")
    data: List[ViewAccount] = Field(..., description="List of accounts with bracket, portfolio, and TWRR details")


class AccountUpdateRequest(BaseModel):
    account_id: str = Field(..., description="ID of the account, e.g. ACC_000001 or JACC_000001")
    account_type: Literal["single", "joint"] = Field(..., description="Either 'single' or 'joint'")
    pf_value: Optional[float] = None
    cash_value: Optional[float] = None
    invested_amt: Optional[float] = None
    total_twrr: Optional[float] = None
    current_yr_twrr: Optional[float] = None
    cagr: Optional[float] = None

class BulkAccountResult(BaseModel):
    row_index: int
    status: str
    detail: str
    account_id: Optional[str] = None

class BulkAccountResponse(BaseModel):
    total_rows: int
    processed_rows: int
    results: list[BulkAccountResult]


