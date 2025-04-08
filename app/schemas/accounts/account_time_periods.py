from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import date, datetime


class AccountTimePeriodsBase(BaseModel):
    owner_id: str = Field(..., description="Single or joint account ID")
    owner_type: Literal["single","joint"] = Field(..., description="Owner type")
    start_date: date = Field(..., description="Start date of the period")
    start_value: float = Field(..., description="Value at the start date")
    end_date: date = Field(..., description="End date of the period")
    end_value: float = Field(..., description="Value at the end date")
    returns: float = Field(..., description="Returns fraction or percent")
    returns_1: Optional[float] = Field(None, description="Optional additional returns metric")

class AccountTimePeriodsCreate(AccountTimePeriodsBase):
    pass

class AccountTimePeriodsUpdate(BaseModel):
    start_date: Optional[date] = None
    start_value: Optional[float] = None
    end_date: Optional[date] = None
    end_value: Optional[float] = None
    returns: Optional[float] = None
    returns_1: Optional[float] = None

class AccountTimePeriodsResponse(AccountTimePeriodsBase):
    time_period_id: int = Field(..., description="Primary key for the time period record")
    created_at: datetime = Field(..., description="Record creation time")

    class Config:
        from_attributes = True
