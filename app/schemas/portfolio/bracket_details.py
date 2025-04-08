from pydantic import BaseModel, Field
from typing import Optional


class BracketBase(BaseModel):
    bracket_min: float = Field(..., description="Minimum investment for bracket")
    bracket_max: float = Field(..., description="Maximum investment for bracket")
    bracket_name: str = Field(..., description="Bracket name or label")

class BracketCreate(BracketBase):
    pass

class BracketUpdate(BaseModel):
    bracket_min: Optional[float] = None
    bracket_max: Optional[float] = None
    bracket_name: Optional[str] = None

class BracketResponse(BracketBase):
    bracket_id: int = Field(..., description="Bracket ID")

    class Config:
        from_attributes = True

