from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.enums import BookingStatus, RoomType


class FacilitySummary(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class TimeSlotSummary(BaseModel):
    id: int
    label: str
    start_time: str
    end_time: str
    order: int

    model_config = ConfigDict(from_attributes=True)


class AvailableRoomItem(BaseModel):
    id: int
    name: str
    block_id: int
    block_name: str
    floor: int
    room_type: RoomType
    capacity: int
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    facilities: List[str] = []
    facility_details: List[FacilitySummary] = []
    fit_score: float

    model_config = ConfigDict(from_attributes=True)


class SuggestionsResponse(BaseModel):
    nearest_free_slots: List[Dict[str, Any]] = []
    other_rooms: List[Dict[str, Any]] = []


class AvailabilityResponse(BaseModel):
    date: date
    slot_ids: List[int]
    total_available: int
    available_rooms: List[AvailableRoomItem]
    suggestions: Optional[SuggestionsResponse] = None


class TimetableCell(BaseModel):
    slot_id: int
    slot_label: str
    status: str  # FREE / BOOKED / CLASS / MAINTENANCE / EXAM
    details: Optional[str] = None


class TimetableRoomRow(BaseModel):
    room_id: int
    room_name: str
    block_id: int
    block_name: str
    floor: int
    capacity: int
    room_type: RoomType
    slots: List[TimetableCell]


class TimetableResponse(BaseModel):
    date: date
    block_id: Optional[int] = None
    slots: List[TimeSlotSummary]
    rooms: List[Dict[str, Any]]
    matrix: List[TimetableRoomRow]
    grid: Dict[str, Dict[str, str]]


class PublicBookingCreate(BaseModel):
    room_id: int
    date: date
    slot_id: int
    purpose: str = Field(..., min_length=3, max_length=500)
    expected_strength: int = Field(..., gt=0)
    required_facilities: List[str] = []
    roll_no: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=255)
    department_id: int
    class_name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=7, max_length=30)
    email: EmailStr


class PublicBookingResponse(BaseModel):
    id: int
    reference: str
    cancel_token: str
    status: BookingStatus
    room_id: int
    room_name: str
    date: date
    slot_id: int
    slot_label: str
    roll_no: str
    name: str
    email: str
    department_id: int
    department_name: Optional[str] = None
    class_name: str
    phone: str
    purpose: str
    expected_strength: int
    required_facilities: List[str] = []
    requires_hod_approval: bool
    created_at: datetime
    message: str

    model_config = ConfigDict(from_attributes=True)


class PublicBookingStatusResponse(BaseModel):
    reference: str
    status: BookingStatus
    room_id: int
    room_name: str
    block_name: Optional[str] = None
    floor: Optional[int] = None
    date: date
    slot_id: int
    slot_label: str
    roll_no: Optional[str] = None
    name: str
    email: str
    phone: str
    department_name: Optional[str] = None
    class_name: Optional[str] = None
    purpose: str
    expected_strength: int
    required_facilities: List[str] = []
    requires_hod_approval: bool
    decision_note: Optional[str] = None
    checked_in: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PublicBookingCancelRequest(BaseModel):
    cancel_token: Optional[str] = None
    reference: Optional[str] = None
    email: Optional[EmailStr] = None
    otp: Optional[str] = None
    reason: Optional[str] = None


class CancelOtpRequest(BaseModel):
    reference: str
    email: EmailStr


class CancelResponse(BaseModel):
    message: str
    reference: str
    status: str
    cancelled_at: datetime


class WaitlistCreate(BaseModel):
    room_id: int
    date: date
    slot_id: int
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    phone: str = Field(..., min_length=7, max_length=30)
    roll_no: Optional[str] = None
    department_id: Optional[int] = None
    class_name: Optional[str] = None


class WaitlistResponse(BaseModel):
    id: int
    room_id: int
    room_name: str
    date: date
    slot_id: int
    slot_label: str
    message: str

