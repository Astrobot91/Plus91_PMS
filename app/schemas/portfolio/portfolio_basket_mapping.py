from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PortfolioBasketMappingBase(BaseModel):
    portfolio_id: int = Field(..., description="Portfolio template ID")
    basket_id: int = Field(..., description="Basket ID")
    allocation_pct: Optional[float] = Field(None, description="Allocation percentage for this basket in the portfolio")

class PortfolioBasketMappingCreate(PortfolioBasketMappingBase):
    pass

class PortfolioBasketMappingUpdate(BaseModel):
    allocation_pct: Optional[float] = None

class PortfolioBasketMappingResponse(PortfolioBasketMappingBase):
    portfolio_basket_mapping_id: int = Field(..., description="Primary key for this mapping")

    class Config:
        from_attributes = True
