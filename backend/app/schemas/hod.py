from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.booking import BookingResponse
from app.schemas.overview import DailyBookingStats, RoomTypeUsageStats


class HodDecisionRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")
    note: Optional[str] = None


class HodPendingApprovalsResponse(BaseModel):
    hod_approval_required: bool
    pending_bookings: List[BookingResponse]
    message: Optional[str] = None


class HodUpcomingBooking(BaseModel):
    id: int
    reference: str
    date: date
    slot_label: str
    start_time: str
    end_time: str
    purpose: str
    requester_name: str
    roll_no: Optional[str] = None
    expected_strength: int
    status: str


class HodLabResponse(BaseModel):
    id: int
    name: str
    block_name: str
    floor: int
    capacity: int
    status: str
    maintenance_note: Optional[str] = None
    facilities: List[str] = []
    total_bookings: int
    upcoming_bookings: List[HodUpcomingBooking] = []
    today_bookings_count: int
    utilization_rate: float


class HodRoomOption(BaseModel):
    id: int
    name: str
    room_type: str
    block_name: str
    capacity: int


class HodSummaryResponse(BaseModel):
    department_id: int
    department_name: str
    department_code: str
    hod_approval_required: bool
    total_rooms: int
    total_labs: int
    bookings_today: int
    pending_approvals_count: int
    utilization_rate: float
    bookings_per_day: List[DailyBookingStats]
    room_type_usage: List[RoomTypeUsageStats]
    recent_bookings: List[BookingResponse] = []
