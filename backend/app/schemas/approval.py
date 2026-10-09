from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field

class ApprovalPolicyResponse(BaseModel):
    id: int
    purpose: str
    requires_hod_approval: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ApprovalPolicyUpdate(BaseModel):
    requires_hod_approval: Optional[bool] = None
    is_active: Optional[bool] = None

class ApprovalDecision(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    remarks: Optional[str] = Field(None, max_length=500)

class BookingApprovalResponse(BaseModel):
    id: int
    booking_id: int
    approver_user_id: int
    decision: str
    remarks: Optional[str] = None
    decided_at: datetime
    model_config = ConfigDict(from_attributes=True)

class HODBookingDetail(BaseModel):
    """Extended booking info for HOD review"""
    id: int
    room_id: int
    title: str
    purpose: Optional[str] = None
    department_id: Optional[int] = None
    start_datetime: datetime
    end_datetime: datetime
    status: str
    requested_by_user_id: Optional[int] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # Nested info
    room_name: Optional[str] = None
    department_name: Optional[str] = None
    requester_username: Optional[str] = None
    approvals: list = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)
