from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class BrokerBase(BaseModel):
    broker_name: str = Field(..., description="Name of the broker")

class BrokerCreate(BrokerBase):
    pass

class BrokerUpdate(BaseModel):
    broker_name: Optional[str] = None

class BrokerResponse(BrokerBase):
    broker_id: str = Field(..., description="Unique ID for the broker")
    created_at: datetime = Field(..., description="Timestamp of record creation")

    class Config:
        from_attributes = True

