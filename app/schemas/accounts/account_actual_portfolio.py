from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


class AccountActualPortfolioBase(BaseModel):
    owner_id: str = Field(..., description="ID of the associated single or joint account")
    owner_type: Literal["single", "joint"] = Field(..., description="Account type indicator")
    trading_symbol: str = Field(..., description="Trading symbol for this holding")
    quantity: float = Field(..., description="Number of units held")
    market_value: float = Field(..., description="Current market value")

class AccountActualPortfolioCreate(AccountActualPortfolioBase):
    pass

class AccountActualPortfolioUpdate(BaseModel):
    quantity: Optional[float] = None
    market_value: Optional[float] = None

class AccountActualPortfolioResponse(AccountActualPortfolioBase):
    created_at: datetime = Field(..., description="Record creation time")

    class Config:
        from_attributes = True
