from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class DistributorBase(BaseModel):
    client_id: Optional[str] = Field(None, description="If a client is also a distributor")
    is_internal: bool = Field(False, description="Is distributor internal or external")
    name: str = Field(..., description="Name of the distributor")
    email_id: Optional[str] = Field(None, description="Email ID")
    country_code: Optional[int] = Field(None, description="Country code")
    phone_no: Optional[int] = Field(None, description="Phone number")
    commission_rate: float = Field(50.0, description="Commission rate in percent")

    @field_validator("phone_no")
    def validate_phone_no(cls, v):
        if v and len(str(v)) > 15:
            raise ValueError("Phone number must be <= 15 digits")
        return v
    
    @field_validator("email_id")
    def validate_email(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and "@" in v:
            return v.lower()
        raise ValueError("Invalid email address")

class DistributorCreate(DistributorBase):
    pass

class DistributorUpdate(BaseModel):
    name: Optional[str] = None
    email_id: Optional[str] = None
    country_code: Optional[int] = None
    phone_no: Optional[int] = None
    is_internal: Optional[bool] = None
    commission_rate: Optional[float] = None

class DistributorResponse(DistributorBase):
    distributor_id: str = Field(..., description="Unique ID for the distributor")
    created_at: datetime = Field(..., description="Timestamp of record creation")

    class Config:
        from_attributes = True

