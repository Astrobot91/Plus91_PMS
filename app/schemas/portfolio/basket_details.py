from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
from datetime import datetime


class BasketBase(BaseModel):
    basket_name: str = Field(..., description="Name of the basket")
    allocation_method: Literal["equal","manual"] = Field(..., description="Method of allocation")

class BasketCreate(BasketBase):
    pass

class BasketUpdate(BaseModel):
    basket_name: Optional[str] = None
    allocation_method: Optional[Literal["equal","manual"]] = None

class BasketResponse(BasketBase):
    basket_id: int = Field(..., description="Basket ID")
    created_at: datetime = Field(..., description="Record creation time")

    class Config:
        from_attributes = True
