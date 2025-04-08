from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PortfolioTemplateBase(BaseModel):
    portfolio_name: str = Field(..., description="Name of the portfolio")
    description: Optional[str] = Field(None, description="Description of the portfolio")

class PortfolioTemplateCreate(PortfolioTemplateBase):
    pass

class PortfolioTemplateUpdate(BaseModel):
    portfolio_name: Optional[str] = None
    description: Optional[str] = None

class PortfolioTemplateResponse(PortfolioTemplateBase):
    portfolio_id: int = Field(..., description="Portfolio template ID")
    created_at: datetime = Field(..., description="Record creation time")

    class Config:
        from_attributes = True
