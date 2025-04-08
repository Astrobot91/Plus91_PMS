from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class JointAccountCreateRequest(BaseModel):
    joint_account_name: str = Field(..., description="Name of the joint account.")
    single_account_ids: List[str] = Field(
        default_factory=list,
        description="List of SingleAccount IDs to link to this joint account."
    )

class JointAccountUpdateRequest(BaseModel):
    joint_account_name: Optional[str] = Field(
        None,
        description="Updated name of the joint account (if changing)."
    )
    single_account_ids: Optional[List[str]] = Field(
        None,
        description="New or updated list of SingleAccount IDs for this joint account."
    )


class JointAccountDeleteRequest(BaseModel):
    joint_account_id: str = Field(..., description="ID of the joint account to delete.")

class JointAccountResponse(BaseModel):
    status: str = Field(..., description="Operation status: 'success' or 'failed'.")
    joint_account_id: str = Field(..., description="Unique ID of the joint account.")
    joint_account_name: Optional[str] = Field(None, description="Name of the joint account.")
    linked_single_accounts: List[str] = Field(
        default_factory=list,
        description="List of single account IDs linked to this joint account."
    )