from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr
from app.models.enums import BookingStatus, RequesterType


class BookingBase(BaseModel):
    room_id: int
    date: date
    slot_id: int
    purpose: str
    expected_strength: int
    required_facilities: List[str] = []
    requester_type: RequesterType
    roll_no: Optional[str] = None
    name: str
    department_id: int
    class_name: Optional[str] = None
    phone: str
    email: EmailStr


class BookingCreate(BookingBase):
    pass


class BookingDecision(BaseModel):
    status: BookingStatus
    decision_note: Optional[str] = None


class BookingResponse(BookingBase):
    id: int
    reference: str
    status: BookingStatus
    requires_hod_approval: bool
    created_at: datetime
    decided_by: Optional[int] = None
    decision_note: Optional[str] = None
    checked_in: bool = False

    model_config = ConfigDict(from_attributes=True)

