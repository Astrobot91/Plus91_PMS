from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime

class AccountBracketBasketAllocationBase(BaseModel):
    account_id: str = Field(..., description="Account ID (single or joint)")
    account_type: Literal["single", "joint"] = Field(..., description="Type of account")
    bracket_id: int = Field(..., description="Bracket ID")
    basket_id: int = Field(..., description="Basket ID")
    allocation_pct: float = Field(..., description="Custom allocation percentage")
    is_custom: bool = Field(..., description="Whether this is a custom allocation")

class AccountBracketBasketAllocationCreate(AccountBracketBasketAllocationBase):
    pass

class AccountBracketBasketAllocationUpdate(BaseModel):
    allocation_pct: Optional[float] = Field(None, description="Updated allocation percentage")
    is_custom: Optional[bool] = Field(None, description="Updated custom flag")

class AccountBracketBasketAllocationResponse(AccountBracketBasketAllocationBase):
    id: int = Field(..., description="Unique identifier for the allocation record")
    created_at: datetime = Field(..., description="Record creation timestamp")

    class Config:
        from_attributes = True