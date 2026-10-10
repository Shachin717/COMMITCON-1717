from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class DailyBookingStats(BaseModel):
    date: str
    day: str
    total: int
    confirmed: int
    pending: int
    rejected: int


class RoomTypeUsageStats(BaseModel):
    room_type: str
    label: str
    room_count: int
    booking_count: int


class AdminOverviewResponse(BaseModel):
    total_rooms: int
    in_maintenance: int
    bookings_today: int
    pending_bookings: int
    utilization_rate: float
    bookings_per_day: List[DailyBookingStats]
    room_type_usage: List[RoomTypeUsageStats]
    recent_activity: List[Dict[str, Any]] = []

