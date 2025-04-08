from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime

class NonTradableLogBase(BaseModel):
    account_id: str = Field(..., description="Account ID")
    trading_symbol: str = Field(..., description="Stock trading symbol")
    reason: Optional[str] = Field(None, description="Reason why the stock is non-tradable")
    event_date: date = Field(..., description="Date of the log entry")

class NonTradableLogCreate(NonTradableLogBase):
    pass

class NonTradableLogUpdate(BaseModel):
    reason: Optional[str] = Field(None, description="Updated reason")

class NonTradableLogResponse(NonTradableLogBase):
    id: int = Field(..., description="Unique identifier for the log entry")
    created_at: datetime = Field(..., description="Record creation timestamp")

    class Config:
        from_attributes = True