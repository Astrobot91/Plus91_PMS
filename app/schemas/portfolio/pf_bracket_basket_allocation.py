from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


class PfBracketBasketAllocationBase(BaseModel):
    owner_id: str = Field(..., description="Owner ID (single or joint)")
    owner_type: Literal["single","joint"] = Field(..., description="Owner type indicator")
    bracket_id: Optional[int] = Field(None, description="Associated bracket ID")
    basket_id: Optional[int] = Field(None, description="Associated basket ID")
    portfolio_id: Optional[int] = Field(None, description="Associated portfolio ID")
    allocation_pct: float = Field(..., description="Allocation percentage")

class PfBracketBasketAllocationCreate(PfBracketBasketAllocationBase):
    pass

class PfBracketBasketAllocationUpdate(BaseModel):
    bracket_id: Optional[int] = None
    basket_id: Optional[int] = None
    portfolio_id: Optional[int] = None
    allocation_pct: Optional[float] = None

class PfBracketBasketAllocationResponse(PfBracketBasketAllocationBase):
    allocation_id: int = Field(..., description="Primary key for this allocation record")
    created_at: datetime = Field(..., description="Record creation time")

    class Config:
        from_attributes = True
