# app/schemas/stock_schemas.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class StockExceptionBase(BaseModel):
    account_id: str = Field(..., description="Account ID (single or joint)")
    trading_symbol: str = Field(..., description="Stock trading symbol")

class StockExceptionCreate(StockExceptionBase):
    pass

class StockExceptionUpdate(BaseModel):
    pass  

class StockExceptionResponse(StockExceptionBase):
    id: int = Field(..., description="Unique identifier for the stock exception")
    created_at: datetime = Field(..., description="Record creation timestamp")

    class Config:
        from_attributes = True