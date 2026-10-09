from datetime import datetime, date, time
from typing import Set, List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class SessionData:
    id: int
    class_group_id: int
    department_id: int
    student_count: int
    session_date: date
    start_time: time
    end_time: time
    required_room_type: str
    required_facility_ids: Set[int] = field(default_factory=set)

    @property
    def start_datetime(self) -> datetime:
        return datetime.combine(self.session_date, self.start_time)

    @property
    def end_datetime(self) -> datetime:
        return datetime.combine(self.session_date, self.end_time)


@dataclass
class RoomData:
    id: int
    name: str
    capacity: int
    room_type: str  # CLASSROOM or LAB
    building_id: Optional[int]
    is_active: bool
    facility_ids: Set[int] = field(default_factory=set)
    authorized_department_ids: Set[int] = field(default_factory=set)  # for LABs


@dataclass
class TimeBlock:
    start_datetime: datetime
    end_datetime: datetime


def intervals_overlap(
    start1: datetime, end1: datetime, start2: datetime, end2: datetime
) -> bool:
    """
    Two intervals overlap when:
    existing_start < requested_end AND requested_start < existing_end.
    Adjacent intervals (end1 == start2) do NOT overlap.
    """
    # Normalize naive/aware if necessary
    if start1.tzinfo is not None and start2.tzinfo is None:
        start1 = start1.replace(tzinfo=None)
        end1 = end1.replace(tzinfo=None)
    elif start2.tzinfo is not None and start1.tzinfo is None:
        start2 = start2.replace(tzinfo=None)
        end2 = end2.replace(tzinfo=None)
    return (start1 < end2) and (start2 < end1)


def is_room_eligible_for_session(room: RoomData, session: SessionData) -> tuple[bool, str]:
    """
    Evaluates hard static eligibility of a room for a session.
    Returns (eligible, reason).
    """
    if not room.is_active:
        return False, "Room is inactive"

    if room.capacity < session.student_count:
        return False, f"Insufficient capacity ({room.capacity} < {session.student_count})"

    if room.room_type != session.required_room_type:
        return False, f"Room type mismatch ({room.room_type} != {session.required_room_type})"

    if not session.required_facility_ids.issubset(room.facility_ids):
        missing = session.required_facility_ids - room.facility_ids
        return False, f"Missing required facilities: {missing}"

    if room.room_type == "LAB":
        if not room.authorized_department_ids:
            return False, "Lab has no authorized departments configured"
        if session.department_id not in room.authorized_department_ids:
            return False, f"Department {session.department_id} unauthorized for lab {room.name}"

    return True, "Eligible"

