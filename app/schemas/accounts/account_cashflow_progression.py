from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import date, datetime

class AccountCashflowProgressionBase(BaseModel):
    owner_id: str = Field(..., description="Owner ID (single or joint account)")
    owner_type: Literal["single", "joint"] = Field(..., description="Type of account owner")
    event_date: date = Field(..., description="Date of the cashflow event")
    cashflow: float = Field(..., description="Cashflow amount")
    portfolio_value: float = Field(..., description="Portfolio value at the event date")
    portfolio_plus_cash: float = Field(..., description="Portfolio value plus cash at the event date")

class AccountCashflowProgressionCreate(AccountCashflowProgressionBase):
    pass

class AccountCashflowProgressionUpdate(BaseModel):
    cashflow: Optional[float] = Field(None, description="Updated cashflow amount")
    portfolio_value: Optional[float] = Field(None, description="Updated portfolio value")
    portfolio_plus_cash: Optional[float] = Field(None, description="Updated portfolio plus cash value")

class AccountCashflowProgressionResponse(AccountCashflowProgressionBase):
    id: int = Field(..., description="Unique identifier for the progression record")
    created_at: datetime = Field(..., description="Record creation timestamp")

    class Config:
        from_attributes = True