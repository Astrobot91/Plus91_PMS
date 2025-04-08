from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import date, datetime


class AccountCashflowBase(BaseModel):
    owner_id: str = Field(..., description="Single or joint account ID")
    owner_type: Literal["single","joint"] = Field(..., description="Owner type")
    event_date: date = Field(..., description="Date of the cashflow")
    cashflow: float = Field(..., description="Cashflow amount")
    tag: Optional[str] = Field(None, description="Additional tag or note")

class AccountCashflowCreate(AccountCashflowBase):
    pass

class AccountCashflowUpdate(BaseModel):
    event_date: Optional[date] = None
    cashflow: Optional[float] = None
    tag: Optional[str] = None

class AccountCashflowResponse(AccountCashflowBase):
    cashflow_id: int = Field(..., description="Primary key for this cashflow record")
    created_at: datetime = Field(..., description="Record creation time")

    class Config:
        from_attributes = True
