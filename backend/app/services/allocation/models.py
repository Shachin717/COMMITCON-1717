from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional, Set, Tuple, Union
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.enums import BookingStatus, RoomStatus, RoomType
from app.models.room import Room
from app.models.room_block import RoomBlock
from app.models.timetable import TimetableEntry
from app.models.booking import Booking


@dataclass
class RoomCandidate:
    id: int
    name: str
    block_id: int
    block_name: str
    floor: int
    room_type: RoomType
    capacity: int
    department_id: Optional[int] = None
    status: RoomStatus = RoomStatus.ACTIVE
    facilities: List[str] = field(default_factory=list)

    @property
    def facilities_set(self) -> Set[str]:
        return {f.lower().strip() for f in self.facilities if f}


@dataclass
class RequestItem:
    id: Union[int, str]
    date: date
    slot_id: int
    expected_strength: int
    room_type: Optional[RoomType] = RoomType.CLASSROOM
    required_facilities: List[str] = field(default_factory=list)
    department_id: Optional[int] = None
    preferred_block_id: Optional[int] = None
    preferred_floor: Optional[int] = None
    created_at: Optional[datetime] = None
    requester_id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    purpose: Optional[str] = None
    booking_id: Optional[int] = None

    @property
    def facilities_set(self) -> Set[str]:
        return {f.lower().strip() for f in self.required_facilities if f}


@dataclass
class Assignment:
    request: RequestItem
    room: Optional[RoomCandidate] = None
    allocated: bool = False
    cost: float = 0.0
    reason_if_unallocated: Optional[str] = None


def room_to_candidate(room: Room) -> RoomCandidate:
    facilities = [f.name for f in room.facilities] if room.facilities else []
    block_name = room.block.name if room.block else f"Block {room.block_id}"
    return RoomCandidate(
        id=room.id,
        name=room.name,
        block_id=room.block_id,
        block_name=block_name,
        floor=room.floor,
        room_type=room.room_type,
        capacity=room.capacity,
        department_id=room.department_id,
        status=room.status,
        facilities=facilities,
    )


def booking_to_request_item(booking: Booking) -> RequestItem:
    req_type = RoomType.CLASSROOM
    if booking.room:
        req_type = booking.room.room_type

    # Home block for requester department if available
    preferred_block_id = None
    if booking.room and booking.room.block_id:
        preferred_block_id = booking.room.block_id

    return RequestItem(
        id=booking.id,
        date=booking.date,
        slot_id=booking.slot_id,
        expected_strength=booking.expected_strength,
        room_type=req_type,
        required_facilities=booking.required_facilities or [],
        department_id=booking.department_id,
        preferred_block_id=preferred_block_id,
        preferred_floor=booking.room.floor if booking.room else None,
        created_at=booking.created_at,
        requester_id=booking.roll_no or booking.email or str(booking.id),
        name=booking.name,
        email=booking.email,
        purpose=booking.purpose,
        booking_id=booking.id,
    )


def load_room_candidates(db: Session) -> List[RoomCandidate]:
    rooms = db.query(Room).all()
    return [room_to_candidate(r) for r in rooms]


def load_unavailable_slots(
    db: Session,
    start_date: date,
    end_date: date,
    exclude_booking_ids: Optional[Set[int]] = None,
) -> Set[Tuple[int, date, int]]:
    """
    Returns a set of (room_id, date, slot_id) triples that are unavailable due to:
    1. RoomBlock (maintenance, exam, institutional block)
    2. TimetableEntry (weekly class schedule)
    3. Existing active Bookings (PENDING, COORDINATOR_APPROVED, APPROVED)
    """
    unavailable: Set[Tuple[int, date, int]] = set()

    # 1. Room blocks
    blocks = (
        db.query(RoomBlock)
        .filter(
            RoomBlock.date >= start_date,
            RoomBlock.date <= end_date,
            RoomBlock.is_released.is_(False),
        )
        .all()
    )
    for b in blocks:
        if b.slot_id is None:
            # Whole day block across all slots (1 to 8)
            for s in range(1, 9):
                unavailable.add((b.room_id, b.date, s))
        else:
            unavailable.add((b.room_id, b.date, b.slot_id))

    # 2. Timetable entries
    timetables = db.query(TimetableEntry).all()
    # Check each date in the range
    curr_date = start_date
    from datetime import timedelta
    while curr_date <= end_date:
        weekday = curr_date.weekday()
        for tt in timetables:
            if tt.day_of_week == weekday:
                unavailable.add((tt.room_id, curr_date, tt.slot_id))
        curr_date += timedelta(days=1)

    # 3. Existing active bookings
    active_statuses = [
        BookingStatus.PENDING,
        BookingStatus.COORDINATOR_APPROVED,
        BookingStatus.APPROVED,
    ]
    query = (
        db.query(Booking)
        .filter(
            Booking.date >= start_date,
            Booking.date <= end_date,
            Booking.status.in_(active_statuses),
        )
    )
    if exclude_booking_ids:
        query = query.filter(~Booking.id.in_(exclude_booking_ids))

    existing_bookings = query.all()
    for eb in existing_bookings:
        unavailable.add((eb.room_id, eb.date, eb.slot_id))

    return unavailable

