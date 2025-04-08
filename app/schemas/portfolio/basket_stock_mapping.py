from pydantic import BaseModel, Field
from typing import Optional


class BasketStockMappingBase(BaseModel):
    basket_id: int = Field(..., description="Basket ID to which the stock belongs")
    trading_symbol: str = Field(..., description="Stock trading symbol")
    multiplier: float = Field(..., description="Multiplier or weight for this stock")

class BasketStockMappingCreate(BasketStockMappingBase):
    pass

class BasketStockMappingUpdate(BaseModel):
    trading_symbol: Optional[str] = None
    multiplier: Optional[float] = None

class BasketStockMappingResponse(BaseModel):
    basket_stock_mapping_id: int = Field(..., description="Primary key of basket-stock mapping")
    basket_name: str = Field(..., description="Name of the basket")
    basket_id: int = Field(..., description="Basket ID to which the stock belongs")
    trading_symbol: str = Field(..., description="Stock trading symbol")
    multiplier: float = Field(..., description="Multiplier or weight for this stock")

    class Config:
        from_attributes = True
