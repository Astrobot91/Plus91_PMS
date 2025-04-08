from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class StockLTPBase(BaseModel):
    trading_symbol: str = Field(..., description="Stock trading symbol")
    ltp: float = Field(..., description="Last traded price")

class StockLTPCreate(StockLTPBase):
    pass

class StockLTPUpdate(BaseModel):
    ltp: Optional[float] = Field(None, description="Updated last traded price")

class StockLTPResponse(StockLTPBase):
    id: int = Field(..., description="Unique identifier for the stock LTP record")
    created_at: datetime = Field(..., description="Record creation timestamp")

    class Config:
        from_attributes = True