from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import BookingStatus


class FacultyBookingCreate(BaseModel):
    room_id: int
    date: date
    slot_id: int
    purpose: str = Field(..., min_length=3, max_length=500)
    expected_strength: int = Field(..., gt=0)
    required_facilities: List[str] = []
    faculty_id: Optional[str] = None  # Stored in roll_no column
    class_name: Optional[str] = "Academic Lecture / Lab"
    phone: Optional[str] = None


class FacultyPendingCountResponse(BaseModel):
    pending_count: int
    total_bookings: int


class FacultyCancelResponse(BaseModel):
    message: str
    reference: str
    status: str
    cancelled_at: datetime

