from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


class AccountIdealPortfolioBase(BaseModel):
    owner_id: str = Field(..., description="Owner ID (single account or joint account)")
    owner_type: Literal["single", "joint"] = Field(..., description="Indicates single or joint")
    basket: str = Field(..., description="Name of the basket or strategy")
    trading_symbol: str = Field(..., description="Stock trading symbol")
    allocation_pct: float = Field(..., description="Allocation percentage")
    investment_amount: float = Field(..., description="Investment amount in currency")

class AccountIdealPortfolioCreate(AccountIdealPortfolioBase):
    pass

class AccountIdealPortfolioUpdate(BaseModel):
    basket: Optional[str] = None
    trading_symbol: Optional[str] = None
    allocation_pct: Optional[float] = None
    investment_amount: Optional[float] = None

class AccountIdealPortfolioResponse(AccountIdealPortfolioBase):
    ideal_portfolio_id: int = Field(..., description="Unique ID for the ideal portfolio record")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        from_attributes = True
