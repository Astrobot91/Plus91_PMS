from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date

class HistStockPriceBase(BaseModel):
    trading_symbol: str = Field(..., description="Stock trading symbol")
    snapshot_date: date = Field(..., description="Date of the price snapshot")
    open: float = Field(..., description="Opening price of the stock")
    high: float = Field(..., description="Highest price of the stock")
    low: float = Field(..., description="Lowest price of the stock")
    close: float = Field(..., description="Closing price of the stock")

class HistStockPriceCreate(HistStockPriceBase):
    pass

class HistStockPriceUpdate(BaseModel):
    open: Optional[float] = Field(None, description="Updated opening price of the stock")
    high: Optional[float] = Field(None, description="Updated highest price of the stock")
    low: Optional[float] = Field(None, description="Updated lowest price of the stock")
    close: Optional[float] = Field(None, description="Updated closing price of the stock")

class HistStockPriceResponse(HistStockPriceBase):
    updated_at: datetime = Field(..., description="Timestamp of the last update to the record")

    class Config:
        from_attributes = True