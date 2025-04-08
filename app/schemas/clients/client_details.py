import re
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List


class ClientListResponse(BaseModel):
    client_id: str = Field(..., description="Unique client identifier")
    account_id: Optional[str] = Field(..., description="Unique Account identifier")
    client_name: str = Field(..., description="Legal name of client")
    broker_name: str = Field(..., description="Associated broker name")
    broker_code: Optional[str] = Field(..., description="Associated broker code")
    broker_passwd: Optional[str] = Field(..., description="Password of the broker account")
    distributor_name: Optional[str] = Field(None, description="Distributor reference")
    pan_no: str = Field(..., description="PAN card number")
    country_code: Optional[str] = Field(None, description="Dialing code prefix")
    phone_no: Optional[str] = Field(None, description="Primary contact number")
    email_id: Optional[str] = Field(None, description="Registered email")
    addr: Optional[str] = Field(None, description="Current address")
    acc_start_date: Optional[str] = Field(None, description="Account activation date")
    type: Optional[str] = Field(None, description="Client classification")
    onboard_status: Optional[str] = Field(..., description="Active | Pending | Suspended")
    created_at: datetime = Field(..., description="Record creation timestamp")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "client_id": "CLIENT_0001",
                "account_id": "ACC_00001",
                "client_name": "Acme Corp",
                "broker_name": "TradeMaster",
                "broker_code": "XXXXXX",
                "broker_passwd": "somepassword?",
                "distributor_name": "FinDistro",
                "pan_no": "ABCDE1234F",
                "country_code": "91",
                "phone_no": "9876543210",
                "email_id": "contact@acme.com",
                "addr": "Mumbai, India",
                "acc_start_date": "2024-01-01",
                "type": "Institutional",
                "onboard_status": "active",
                "created_at": "2024-03-15T12:34:56"
            }
        }

class ClientCreateRequest(BaseModel):
    """
    Request schema for creating or updating a client in bulk.
    Also used for partial updates if 'client_id' is present.
    """
    client_id: Optional[str] = None  # only used for update
    client_name: Optional[str] = Field(None, description="Name of the client (required for create)")
    broker_name: Optional[str] = Field(None, description="Name of the existing broker (required for create)")
    pan_no: Optional[str] = Field(None, description="PAN number (required for create)")
    broker_code: Optional[str] = None
    broker_passwd: Optional[str] = None
    email_id: Optional[str] = None
    country_code: Optional[str] = None
    phone_no: Optional[str] = None
    addr: Optional[str] = None
    acc_start_date: Optional[str] = None
    distributor_name: Optional[str] = None  # optional
    alias_name: Optional[str] = None
    alias_phone_no: Optional[str] = None
    alias_addr: Optional[str] = None
    type: Optional[str] = None

class BulkClientResult(BaseModel):
    """
    Indicates success/failure for a single row in a bulk operation.
    """
    row_index: int
    status: str  # "success" or "failed"
    detail: str
    client_id: Optional[str] = None

class BulkClientResponse(BaseModel):
    """
    Summarizes the entire bulk operation (create/update/delete).
    """
    total_rows: int
    processed_rows: int
    results: List[BulkClientResult]


