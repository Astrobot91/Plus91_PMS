from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


class AccountPerformanceBase(BaseModel):
    owner_id: str = Field(..., description="Single or joint account ID")
    owner_type: Literal["single","joint"] = Field(..., description="Owner type")
    total_twrr: Optional[float] = Field(None, description="Total time-weighted return")
    current_yr_twrr: Optional[float] = Field(None, description="Current year's TWRR")
    cagr: Optional[float] = Field(None, description="Compound annual growth rate")

class AccountPerformanceCreate(AccountPerformanceBase):
    performance_id: str = Field(..., description="Unique performance ID if not system-generated")

class AccountPerformanceUpdate(BaseModel):
    total_twrr: Optional[float] = None
    current_yr_twrr: Optional[float] = None
    cagr: Optional[float] = None

class AccountPerformanceResponse(AccountPerformanceBase):
    performance_id: str = Field(..., description="Unique performance ID")
    created_at: datetime = Field(..., description="Record creation time")

    class Config:
        from_attributes = True
