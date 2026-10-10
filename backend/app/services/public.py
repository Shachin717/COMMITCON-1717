import hashlib
import logging
import re
import secrets
import threading
import time as time_mod
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.core.security import generate_numeric_otp, generate_secure_token, hash_token, verify_otp
from app.models.audit_log import AuditLog
from app.models.block import Block
from app.models.booking import Booking
from app.models.department import Department
from app.models.enums import BookingStatus, RequesterType, RoomBlockReason, RoomStatus, RoomType
from app.models.facility import Facility
from app.models.otp import OtpCode
from app.models.room import Room
from app.models.room_block import RoomBlock
from app.models.time_slot import TimeSlot
from app.models.timetable import TimetableEntry
from app.models.waitlist import WaitlistEntry
from app.schemas.public import (
    AvailableRoomItem,
    FacilitySummary,
    PublicBookingCancelRequest,
    PublicBookingCreate,
    SuggestionsResponse,
    TimetableCell,
    TimetableResponse,
    TimetableRoomRow,
    TimeSlotSummary,
    WaitlistCreate,
)
from app.services.audit import log_audit
from app.services.email import (
    send_booking_acknowledgement_email,
    send_booking_cancellation_email,
    send_cancellation_otp_email,
    send_waitlist_notification_email,
)


class AvailabilityConflictException(HTTPException):
    def __init__(self, message: str, suggestions: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": message,
                "suggestions": suggestions or {},
            },
        )


def calculate_fit_score(
    room_capacity: int,
    required_capacity: Optional[int],
    room_facility_names: List[str],
    required_facilities: Optional[List[str]],
) -> float:
    """
    Calculate allocation fit score (0 - 100).
    Rule: Best-fit capacity first (minimizing wasted seats), then facility match.
    """
    # 1. Capacity Fit
    if required_capacity and required_capacity > 0:
        if room_capacity < required_capacity:
            # Insufficient capacity
            capacity_score = 0.0
        else:
            # Closer room capacity is to required capacity, the better (less wastage)
            # 1.0 if exact, decreases as room is unnecessarily larger
            capacity_score = (required_capacity / room_capacity) * 100.0
    else:
        # If no capacity requested, baseline capacity score
        capacity_score = 100.0

    # 2. Facility Match
    clean_req_facilities = [
        f.lower().strip() for f in (required_facilities or []) if f.strip()
    ]
    if clean_req_facilities:
        clean_room_facilities = {f.lower().strip() for f in room_facility_names}
        matched_count = sum(1 for req in clean_req_facilities if req in clean_room_facilities)
        facility_score = (matched_count / len(clean_req_facilities)) * 100.0
    else:
        facility_score = 100.0

    # Best-fit capacity first (65% weight), then facility match (35% weight)
    fit_score = (0.65 * capacity_score) + (0.35 * facility_score)
    return round(fit_score, 2)


def check_room_availability(
    db: Session,
    room: Room,
    target_date: date,
    slot_ids: List[int],
) -> Tuple[bool, Optional[str]]:
    """
    Check if a room is available for a date across the given time slots.
    A room is available iff:
    1. Room is ACTIVE
    2. No RoomBlock for that date and slot (or entire day)
    3. No TimetableEntry for that day of week and slot
    4. No active Booking (PENDING, COORDINATOR_APPROVED, APPROVED)
    """
    if room.status != RoomStatus.ACTIVE:
        return False, f"Room {room.name} is under maintenance"

    # 1. Check RoomBlocks
    block_conflict = (
        db.query(RoomBlock)
        .filter(
            RoomBlock.room_id == room.id,
            RoomBlock.date == target_date,
            RoomBlock.is_released.is_(False),
            or_(RoomBlock.slot_id.is_(None), RoomBlock.slot_id.in_(slot_ids)),
        )
        .first()
    )
    if block_conflict:
        reason_label = block_conflict.reason.value if hasattr(block_conflict.reason, "value") else str(block_conflict.reason)
        return False, f"Room {room.name} is blocked for {reason_label}"

    # 2. Check TimetableEntries
    weekday = target_date.weekday()
    timetable_conflict = (
        db.query(TimetableEntry)
        .filter(
            TimetableEntry.room_id == room.id,
            TimetableEntry.day_of_week == weekday,
            TimetableEntry.slot_id.in_(slot_ids),
        )
        .first()
    )
    if timetable_conflict:
        return False, f"Room {room.name} has a recurring class: {timetable_conflict.subject}"

    # 3. Check active Bookings
    active_booking_conflict = (
        db.query(Booking)
        .filter(
            Booking.room_id == room.id,
            Booking.date == target_date,
            Booking.slot_id.in_(slot_ids),
            Booking.status.in_([
                BookingStatus.PENDING,
                BookingStatus.COORDINATOR_APPROVED,
                BookingStatus.APPROVED,
            ]),
        )
        .first()
    )
    if active_booking_conflict:
        return False, f"Room {room.name} is already booked ({active_booking_conflict.reference})"

    return True, None


def get_availability_suggestions(
    db: Session,
    target_date: date,
    slot_ids: List[int],
    min_capacity: Optional[int] = None,
    facilities: Optional[List[str]] = None,
    room_type: Optional[RoomType] = None,
    block_id: Optional[int] = None,
    department_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    When no rooms are available for the exact query, find nearest free slots on the same day
    and alternative rooms that meet most requirements.
    """
    all_slots = db.query(TimeSlot).order_by(TimeSlot.order).all()
    if not all_slots:
        return {"nearest_free_slots": [], "other_rooms": []}

    target_slot_set = set(slot_ids)
    target_orders = [s.order for s in all_slots if s.id in target_slot_set]
    avg_target_order = sum(target_orders) / len(target_orders) if target_orders else 1

    # 1. Nearest free slots on the same day
    other_slots = [s for s in all_slots if s.id not in target_slot_set]
    # Sort slots by distance to target slot order
    other_slots.sort(key=lambda s: abs(s.order - avg_target_order))

    all_active_rooms = (
        db.query(Room)
        .options(joinedload(Room.block), joinedload(Room.facilities))
        .filter(Room.status == RoomStatus.ACTIVE)
        .all()
    )

    nearest_free_slots = []
    for slot in other_slots[:4]:  # inspect up to 4 closest slots
        slot_free_rooms = []
        for room in all_active_rooms:
            # apply basic filters if feasible
            if min_capacity and room.capacity < min_capacity:
                continue
            if room_type and room.room_type != room_type:
                continue
            avail, _ = check_room_availability(db, room, target_date, [slot.id])
            if avail:
                fac_names = [f.name for f in room.facilities]
                score = calculate_fit_score(room.capacity, min_capacity, fac_names, facilities)
                slot_free_rooms.append({
                    "room_id": room.id,
                    "room_name": room.name,
                    "block_name": room.block.name if room.block else "",
                    "capacity": room.capacity,
                    "fit_score": score,
                })

        if slot_free_rooms:
            slot_free_rooms.sort(key=lambda r: r["fit_score"], reverse=True)
            nearest_free_slots.append({
                "slot_id": slot.id,
                "slot_label": slot.label,
                "start_time": str(slot.start_time),
                "end_time": str(slot.end_time),
                "available_rooms_count": len(slot_free_rooms),
                "rooms": slot_free_rooms[:3],
            })

    # 2. Other rooms on the requested slots (e.g. relax block_id, relax facilities, or slightly smaller/larger)
    other_rooms = []
    for room in all_active_rooms:
        avail, _ = check_room_availability(db, room, target_date, slot_ids)
        if not avail:
            continue

        fac_names = [f.name for f in room.facilities]
        score = calculate_fit_score(room.capacity, min_capacity, fac_names, facilities)
        
        reasons = []
        if block_id and room.block_id != block_id:
            reasons.append(f"Located in {room.block.name if room.block else 'another block'}")
        if min_capacity and room.capacity < min_capacity:
            reasons.append(f"Capacity {room.capacity} (below requested {min_capacity})")
        elif min_capacity and room.capacity >= min_capacity:
            reasons.append(f"Adequate capacity ({room.capacity} seats)")
        if facilities:
            matched = sum(1 for req in facilities if req.lower() in [f.name.lower() for f in room.facilities])
            reasons.append(f"Matches {matched}/{len(facilities)} requested facilities")

        other_rooms.append({
            "room_id": room.id,
            "room_name": room.name,
            "block_name": room.block.name if room.block else "",
            "floor": room.floor,
            "capacity": room.capacity,
            "room_type": room.room_type.value,
            "fit_score": score,
            "facilities": fac_names,
            "recommendation_reason": "; ".join(reasons) if reasons else "Alternative active room",
        })

    other_rooms.sort(key=lambda r: r["fit_score"], reverse=True)

    return {
        "nearest_free_slots": nearest_free_slots[:3],
        "other_rooms": other_rooms[:5],
    }


def query_availability(
    db: Session,
    target_date: date,
    slot_ids: List[int],
    min_capacity: Optional[int] = None,
    facilities: Optional[List[str]] = None,
    room_type: Optional[RoomType] = None,
    block_id: Optional[int] = None,
    department_id: Optional[int] = None,
) -> Tuple[List[AvailableRoomItem], Optional[Dict[str, Any]]]:
    """
    Search available rooms matching filters, sort by fit score.
    If no rooms available, populate suggestions.
    """
    if not slot_ids:
        # Default to all slots if none provided
        all_slots = db.query(TimeSlot.id).all()
        slot_ids = [s[0] for s in all_slots]

    query = (
        db.query(Room)
        .options(
            joinedload(Room.block),
            joinedload(Room.department),
            joinedload(Room.facilities),
        )
        .filter(Room.status == RoomStatus.ACTIVE)
    )

    if block_id is not None:
        query = query.filter(Room.block_id == block_id)
    if room_type is not None:
        query = query.filter(Room.room_type == room_type)
    if department_id is not None:
        query = query.filter(Room.department_id == department_id)
    if min_capacity is not None and min_capacity > 0:
        query = query.filter(Room.capacity >= min_capacity)

    candidates = query.all()

    clean_req_facilities = [
        f.lower().strip() for f in (facilities or []) if f.strip()
    ]

    available_rooms: List[AvailableRoomItem] = []

    for room in candidates:
        room_fac_names = [fac.name for fac in room.facilities]
        room_fac_names_lower = [f.lower().strip() for f in room_fac_names]

        # If user explicitly required facilities, require that all requested facilities are present
        if clean_req_facilities:
            has_all_facs = all(req in room_fac_names_lower for req in clean_req_facilities)
            if not has_all_facs:
                continue

        # Check availability against blocks, timetable, and bookings
        is_avail, _ = check_room_availability(db, room, target_date, slot_ids)
        if not is_avail:
            continue

        fit_score = calculate_fit_score(
            room_capacity=room.capacity,
            required_capacity=min_capacity,
            room_facility_names=room_fac_names,
            required_facilities=clean_req_facilities,
        )

        facility_summaries = [
            FacilitySummary(id=fac.id, name=fac.name) for fac in room.facilities
        ]

        item = AvailableRoomItem(
            id=room.id,
            name=room.name,
            block_id=room.block_id,
            block_name=room.block.name if room.block else "",
            floor=room.floor,
            room_type=room.room_type,
            capacity=room.capacity,
            department_id=room.department_id,
            department_name=room.department.name if room.department else None,
            facilities=room_fac_names,
            facility_details=facility_summaries,
            fit_score=fit_score,
        )
        available_rooms.append(item)

    # Sort rooms with best fit score first (best-fit capacity first, then facility match)
    available_rooms.sort(key=lambda r: r.fit_score, reverse=True)

    suggestions = None
    if not available_rooms:
        suggestions = get_availability_suggestions(
            db=db,
            target_date=target_date,
            slot_ids=slot_ids,
            min_capacity=min_capacity,
            facilities=clean_req_facilities,
            room_type=room_type,
            block_id=block_id,
            department_id=department_id,
        )

    return available_rooms, suggestions


# In-memory TTL cache for public timetable queries (10-second TTL)
_timetable_cache: Dict[Tuple[str, Optional[int]], Tuple[float, TimetableResponse]] = {}
TIMETABLE_CACHE_TTL = 10.0


def clear_timetable_cache() -> None:
    """Clear cached public timetable responses upon booking or room mutations."""
    _timetable_cache.clear()


def get_public_timetable(
    db: Session,
    target_date: date,
    block_id: Optional[int] = None,
) -> TimetableResponse:
    """
    Build grid (rooms x slots) showing FREE / BOOKED / CLASS / MAINTENANCE / EXAM per cell.
    Cached for a few seconds to avoid high database load from frequent timetable refreshes.
    """
    cache_key = (target_date.isoformat(), block_id)
    now = time_mod.monotonic()
    if cache_key in _timetable_cache:
        cached_time, cached_resp = _timetable_cache[cache_key]
        if now - cached_time < TIMETABLE_CACHE_TTL:
            return cached_resp

    slots = db.query(TimeSlot).order_by(TimeSlot.order).all()
    slot_summaries = [
        TimeSlotSummary(
            id=s.id,
            label=s.label,
            start_time=str(s.start_time),
            end_time=str(s.end_time),
            order=s.order,
        )
        for s in slots
    ]
    slot_id_to_slot = {s.id: s for s in slots}

    room_query = db.query(Room).options(joinedload(Room.block)).order_by(Room.name)
    if block_id is not None:
        room_query = room_query.filter(Room.block_id == block_id)
    rooms = room_query.all()

    # Pre-fetch room blocks for date
    room_blocks = (
        db.query(RoomBlock)
        .filter(RoomBlock.date == target_date, RoomBlock.is_released.is_(False))
        .all()
    )
    # Map (room_id, slot_id) or (room_id, None) -> RoomBlock
    blocks_map: Dict[Tuple[int, Optional[int]], RoomBlock] = {}
    for rb in room_blocks:
        blocks_map[(rb.room_id, rb.slot_id)] = rb

    # Pre-fetch timetable classes for this weekday
    weekday = target_date.weekday()
    timetable_entries = (
        db.query(TimetableEntry)
        .filter(TimetableEntry.day_of_week == weekday)
        .all()
    )
    timetable_map: Dict[Tuple[int, int], TimetableEntry] = {}
    for te in timetable_entries:
        timetable_map[(te.room_id, te.slot_id)] = te

    # Pre-fetch active bookings for date
    bookings = (
        db.query(Booking)
        .filter(
            Booking.date == target_date,
            Booking.status.in_([
                BookingStatus.PENDING,
                BookingStatus.COORDINATOR_APPROVED,
                BookingStatus.APPROVED,
            ]),
        )
        .all()
    )
    bookings_map: Dict[Tuple[int, int], Booking] = {}
    for b in bookings:
        bookings_map[(b.room_id, b.slot_id)] = b

    matrix: List[TimetableRoomRow] = []
    grid: Dict[str, Dict[str, str]] = {}
    room_list = []

    for r in rooms:
        room_info = {
            "id": r.id,
            "name": r.name,
            "block_id": r.block_id,
            "block_name": r.block.name if r.block else "",
            "floor": r.floor,
            "capacity": r.capacity,
            "room_type": r.room_type.value,
            "status": r.status.value,
        }
        room_list.append(room_info)

        row_cells: List[TimetableCell] = []
        grid_row: Dict[str, str] = {}

        for s in slots:
            # Determine status priority
            cell_status = "FREE"
            cell_details = None

            if r.status == RoomStatus.MAINTENANCE:
                cell_status = "MAINTENANCE"
                cell_details = r.maintenance_note or "Room under maintenance"
            elif (r.id, None) in blocks_map:
                rb = blocks_map[(r.id, None)]
                cell_status = "EXAM" if rb.reason == RoomBlockReason.EXAM else "MAINTENANCE"
                cell_details = rb.note or f"Full-day block ({rb.reason.value})"
            elif (r.id, s.id) in blocks_map:
                rb = blocks_map[(r.id, s.id)]
                cell_status = "EXAM" if rb.reason == RoomBlockReason.EXAM else "MAINTENANCE"
                cell_details = rb.note or f"Slot block ({rb.reason.value})"
            elif (r.id, s.id) in timetable_map:
                te = timetable_map[(r.id, s.id)]
                cell_status = "CLASS"
                cell_details = f"{te.subject} ({te.faculty_name})"
            elif (r.id, s.id) in bookings_map:
                bk = bookings_map[(r.id, s.id)]
                cell_status = "BOOKED"
                cell_details = f"Booked: {bk.purpose}"

            row_cells.append(
                TimetableCell(
                    slot_id=s.id,
                    slot_label=s.label,
                    status=cell_status,
                    details=cell_details,
                )
            )
            grid_row[str(s.id)] = cell_status

        matrix.append(
            TimetableRoomRow(
                room_id=r.id,
                room_name=r.name,
                block_id=r.block_id,
                block_name=r.block.name if r.block else "",
                floor=r.floor,
                capacity=r.capacity,
                room_type=r.room_type,
                slots=row_cells,
            )
        )
        grid[str(r.id)] = grid_row

    response = TimetableResponse(
        date=target_date,
        block_id=block_id,
        slots=slot_summaries,
        rooms=room_list,
        matrix=matrix,
        grid=grid,
    )
    _timetable_cache[cache_key] = (now, response)
    return response


def validate_booking_inputs(db: Session, booking_in: PublicBookingCreate) -> Tuple[Room, TimeSlot, Department]:
    """Validate student details, department, room, slot, and date."""
    # 1. Roll No validation
    if not booking_in.roll_no or not booking_in.roll_no.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Valid Roll Number is required for student room allocation.",
        )

    # 2. Name validation
    if not booking_in.name or not booking_in.name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Student name is required.",
        )

    # 3. Class validation
    if not booking_in.class_name or not booking_in.class_name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Class/Section is required.",
        )

    # 4. Phone validation
    phone_clean = re.sub(r"[\s\-\+\(\)]", "", booking_in.phone)
    if not phone_clean.isdigit() or len(phone_clean) < 7:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please provide a valid contact phone number.",
        )

    # 5. Date validation
    if booking_in.date < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot book a room for a past date.",
        )

    # 6. Entity existence
    room = db.query(Room).options(joinedload(Room.department), joinedload(Room.block)).filter(Room.id == booking_in.room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specified room does not exist.")

    slot = db.query(TimeSlot).filter(TimeSlot.id == booking_in.slot_id).first()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specified time slot does not exist.")

    dept = db.query(Department).filter(Department.id == booking_in.department_id).first()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specified department does not exist.")

    if booking_in.expected_strength > room.capacity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expected strength ({booking_in.expected_strength}) exceeds room capacity ({room.capacity}).",
        )

    return room, slot, dept


def generate_unique_reference(db: Session) -> str:
    """Generate collision-resistant alphanumeric reference code."""
    for _ in range(10):
        ref = f"BK-{secrets.token_hex(4).upper()}"
        if not db.query(Booking.id).filter(Booking.reference == ref).first():
            return ref
    # Fallback to timestamp-augmented reference
    return f"BK-{int(datetime.now().timestamp())}-{secrets.token_hex(2).upper()}"


_booking_lock = threading.Lock()


def _send_ack_email(
    to_email: str,
    reference: str,
    cancel_token: str,
    student_name: str,
    room_name: str,
    date_str: str,
    slot_label: str,
    purpose: str,
    expected_strength: int,
    requires_hod_approval: bool,
):
    try:
        success = send_booking_acknowledgement_email(
            to_email=to_email,
            reference=reference,
            cancel_token=cancel_token,
            student_name=student_name,
            room_name=room_name,
            date_str=date_str,
            slot_label=slot_label,
            purpose=purpose,
            expected_strength=expected_strength,
            requires_hod_approval=requires_hod_approval,
        )
        if not success:
            logger.error(f"Failed to dispatch acknowledgement email for {reference} to {to_email}")
    except Exception as exc:
        logger.error(f"Error dispatching acknowledgement email for booking {reference}: {exc}", exc_info=True)


def create_public_booking(
    db: Session,
    booking_in: PublicBookingCreate,
    background_tasks: Optional[BackgroundTasks] = None,
) -> Tuple[Booking, str]:
    """
    Validate details, verify availability inside a transaction, handle DB exclusion constraints,
    create PENDING booking, generate secure cancel token & reference, and send ACK email in background.
    """
    room, slot, dept = validate_booking_inputs(db, booking_in)

    with _booking_lock:
        # Check availability inside transaction
        is_avail, conflict_reason = check_room_availability(
            db, room, booking_in.date, [booking_in.slot_id]
        )
        if not is_avail:
            suggestions = get_availability_suggestions(
                db=db,
                target_date=booking_in.date,
                slot_ids=[booking_in.slot_id],
                min_capacity=booking_in.expected_strength,
                facilities=booking_in.required_facilities,
                room_type=room.room_type,
                block_id=room.block_id,
                department_id=booking_in.department_id,
            )
            raise AvailabilityConflictException(
                message=conflict_reason or "The selected room and time slot is not available.",
                suggestions=suggestions,
            )

        # Determine HOD approval requirement
        # LAB or EXAM_HALL and department has HOD approval enabled
        requires_hod = False
        if room.room_type in (RoomType.LAB, RoomType.EXAM_HALL):
            # check room department or booking department
            dept_to_check = room.department or dept
            if dept_to_check and dept_to_check.hod_approval_required:
                requires_hod = True

        reference = generate_unique_reference(db)
        raw_cancel_token = generate_secure_token(32)
        cancel_hash = hash_token(raw_cancel_token)

        booking = Booking(
            reference=reference,
            room_id=room.id,
            date=booking_in.date,
            slot_id=slot.id,
            purpose=booking_in.purpose.strip(),
            expected_strength=booking_in.expected_strength,
            required_facilities=booking_in.required_facilities,
            status=BookingStatus.PENDING,
            requires_hod_approval=requires_hod,
            requester_type=RequesterType.STUDENT,
            roll_no=booking_in.roll_no.strip(),
            name=booking_in.name.strip(),
            department_id=dept.id,
            class_name=booking_in.class_name.strip(),
            phone=booking_in.phone.strip(),
            email=str(booking_in.email).strip().lower(),
            cancel_token_hash=cancel_hash,
        )

        try:
            db.add(booking)
            db.commit()
            db.refresh(booking)
        except IntegrityError:
            db.rollback()
            suggestions = get_availability_suggestions(
                db=db,
                target_date=booking_in.date,
                slot_ids=[booking_in.slot_id],
                min_capacity=booking_in.expected_strength,
                facilities=booking_in.required_facilities,
                room_type=room.room_type,
                block_id=room.block_id,
                department_id=booking_in.department_id,
            )
            raise AvailabilityConflictException(
                message=(
                    f"We could not complete your booking for {room.name} at {slot.label}. "
                    "Another user has just reserved this room and slot simultaneously. "
                    "Please choose another time slot or room below."
                ),
                suggestions=suggestions,
            )

    # Dispatch ACK email safely in a background task
    ack_args = (
        booking.email,
        booking.reference,
        raw_cancel_token,
        booking.name,
        room.name,
        str(booking.date),
        slot.label,
        booking.purpose,
        booking.expected_strength,
        booking.requires_hod_approval,
    )
    if background_tasks is not None:
        background_tasks.add_task(_send_ack_email, *ack_args)
    else:
        threading.Thread(target=_send_ack_email, args=ack_args, daemon=True).start()

    clear_timetable_cache()
    return booking, raw_cancel_token


def get_booking_by_reference_and_email(
    db: Session,
    reference: str,
    email: str,
) -> Booking:
    """Retrieve booking by unique reference code and email."""
    booking = (
        db.query(Booking)
        .options(
            joinedload(Booking.room).joinedload(Room.block),
            joinedload(Booking.slot),
            joinedload(Booking.department),
        )
        .filter(Booking.reference == reference.strip())
        .first()
    )
    if not booking or booking.email.lower() != email.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found or email verification failed.",
        )
    return booking


def request_cancellation_otp(
    db: Session,
    reference: str,
    email: str,
) -> None:
    """Generate 6-digit OTP for booking cancellation and send via email."""
    booking = get_booking_by_reference_and_email(db, reference, email)
    if booking.status == BookingStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This booking has already been cancelled.",
        )

    otp_code = generate_numeric_otp(6)
    code_hash = hash_token(otp_code)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

    otp_record = OtpCode(
        email=booking.email,
        purpose="booking_cancel",
        code_hash=code_hash,
        expires_at=expires_at,
        attempts=0,
        used=False,
    )
    db.add(otp_record)
    db.commit()

    send_cancellation_otp_email(
        to_email=booking.email,
        reference=booking.reference,
        otp_code=otp_code,
        student_name=booking.name,
    )


def _send_cancellation_email(
    to_email: str,
    reference: str,
    student_name: str,
    room_name: str,
    date_str: str,
    slot_label: str,
):
    try:
        success = send_booking_cancellation_email(
            to_email=to_email,
            reference=reference,
            student_name=student_name,
            room_name=room_name,
            date_str=date_str,
            slot_label=slot_label,
        )
        if not success:
            logger.error(f"Failed to dispatch cancellation email for {reference} to {to_email}")
    except Exception as exc:
        logger.error(f"Error dispatching cancellation email for booking {reference}: {exc}", exc_info=True)


def _send_waitlist_email(
    to_email: str,
    student_name: str,
    room_name: str,
    date_str: str,
    slot_label: str,
):
    try:
        success = send_waitlist_notification_email(
            to_email=to_email,
            student_name=student_name,
            room_name=room_name,
            date_str=date_str,
            slot_label=slot_label,
        )
        if not success:
            logger.error(f"Failed to dispatch waitlist notification email to {to_email}")
    except Exception as exc:
        logger.error(f"Error dispatching waitlist notification email to {to_email}: {exc}", exc_info=True)


def cancel_booking(
    db: Session,
    cancel_req: PublicBookingCancelRequest,
    background_tasks: Optional[BackgroundTasks] = None,
) -> Booking:
    """
    Cancel booking by secure cancel token OR by reference + email OTP.
    Frees slot, sends cancellation email, writes AuditLog, and alerts waitlisted person.
    """
    booking: Optional[Booking] = None
    cancellation_method = ""

    # Path 1: Cancellation by secure token
    if cancel_req.cancel_token and cancel_req.cancel_token.strip():
        token_hash = hash_token(cancel_req.cancel_token.strip())
        booking = (
            db.query(Booking)
            .options(
                joinedload(Booking.room),
                joinedload(Booking.slot),
            )
            .filter(Booking.cancel_token_hash == token_hash)
            .first()
        )
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid or expired cancellation link.",
            )
        cancellation_method = "token"

    # Path 2: Cancellation by Reference + Email (with optional OTP)
    elif cancel_req.reference and cancel_req.email:
        booking = get_booking_by_reference_and_email(
            db, cancel_req.reference, str(cancel_req.email)
        )
        if cancel_req.otp:
            # Verify OTP
            now_utc = datetime.now(timezone.utc)
            otp_entry = (
                db.query(OtpCode)
                .filter(
                    OtpCode.email == booking.email,
                    OtpCode.purpose == "booking_cancel",
                    OtpCode.used.is_(False),
                    OtpCode.expires_at > now_utc,
                )
                .order_by(OtpCode.created_at.desc())
                .first()
            )
            if not otp_entry or not verify_otp(cancel_req.otp.strip(), otp_entry.code_hash):
                if otp_entry:
                    otp_entry.attempts += 1
                    db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired verification OTP.",
                )

            otp_entry.used = True
            cancellation_method = "reference_otp"
        else:
            cancellation_method = "reference_email"

    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either cancel_token or (reference and email) must be provided.",
        )

    if booking.status == BookingStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This booking has already been cancelled.",
        )

    # 1. Update Booking status to CANCELLED and store reason
    booking.status = BookingStatus.CANCELLED
    if cancel_req.reason:
        booking.decision_note = f"Cancellation Reason: {cancel_req.reason.strip()}"
    db.commit()
    db.refresh(booking)

    # 2. Write AuditLog
    log_audit(
        db=db,
        action="BOOKING_CANCELLED",
        entity="Booking",
        entity_id=str(booking.id),
        meta={
            "reference": booking.reference,
            "method": cancellation_method,
            "room_id": booking.room_id,
            "date": str(booking.date),
            "slot_id": booking.slot_id,
            "email": booking.email,
        },
    )

    # 3. Send Cancellation Email safely in background
    cancel_args = (
        booking.email,
        booking.reference,
        booking.name,
        booking.room.name if booking.room else f"Room {booking.room_id}",
        str(booking.date),
        booking.slot.label if booking.slot else f"Slot {booking.slot_id}",
    )
    if background_tasks is not None:
        background_tasks.add_task(_send_cancellation_email, *cancel_args)
    else:
        threading.Thread(target=_send_cancellation_email, args=cancel_args, daemon=True).start()

    # 4. Notify the first waitlisted person safely in background
    waitlist_entry = (
        db.query(WaitlistEntry)
        .filter(
            WaitlistEntry.room_id == booking.room_id,
            WaitlistEntry.date == booking.date,
            WaitlistEntry.slot_id == booking.slot_id,
            WaitlistEntry.notified.is_(False),
        )
        .order_by(WaitlistEntry.created_at.asc())
        .first()
    )

    if waitlist_entry:
        waitlist_args = (
            waitlist_entry.email,
            waitlist_entry.name,
            booking.room.name if booking.room else f"Room {booking.room_id}",
            str(booking.date),
            booking.slot.label if booking.slot else f"Slot {booking.slot_id}",
        )
        if background_tasks is not None:
            background_tasks.add_task(_send_waitlist_email, *waitlist_args)
        else:
            threading.Thread(target=_send_waitlist_email, args=waitlist_args, daemon=True).start()

        waitlist_entry.notified = True
        waitlist_entry.notified_at = datetime.now(timezone.utc)
        db.commit()

        log_audit(
            db=db,
            action="WAITLIST_NOTIFIED",
            entity="WaitlistEntry",
            entity_id=str(waitlist_entry.id),
            meta={
                "room_id": booking.room_id,
                "date": str(booking.date),
                "slot_id": booking.slot_id,
                "waitlist_id": waitlist_entry.id,
                "email": waitlist_entry.email,
            },
        )

    clear_timetable_cache()
    return booking


def join_waitlist(db: Session, waitlist_in: WaitlistCreate) -> WaitlistEntry:
    """Allow student to join the waitlist for a specific occupied room and slot."""
    room = db.query(Room).filter(Room.id == waitlist_in.room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found.")

    slot = db.query(TimeSlot).filter(TimeSlot.id == waitlist_in.slot_id).first()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Time slot not found.")

    if waitlist_in.date < date.today():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot waitlist for a past date.")

    entry = WaitlistEntry(
        room_id=waitlist_in.room_id,
        date=waitlist_in.date,
        slot_id=waitlist_in.slot_id,
        name=waitlist_in.name.strip(),
        email=str(waitlist_in.email).strip().lower(),
        phone=waitlist_in.phone.strip(),
        roll_no=waitlist_in.roll_no.strip() if waitlist_in.roll_no else None,
        department_id=waitlist_in.department_id,
        class_name=waitlist_in.class_name.strip() if waitlist_in.class_name else None,
        notified=False,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    log_audit(
        db=db,
        action="WAITLIST_JOINED",
        entity="WaitlistEntry",
        entity_id=str(entry.id),
        meta={
            "room_id": entry.room_id,
            "date": str(entry.date),
            "slot_id": entry.slot_id,
            "email": entry.email,
        },
    )

    return entry


def get_public_metadata(db: Session) -> Dict[str, Any]:
    """Retrieve all blocks, departments, facilities, and time slots for public search filters."""
    blocks = db.query(Block).order_by(Block.name).all()
    departments = db.query(Department).order_by(Department.name).all()
    facilities = db.query(Facility).order_by(Facility.name).all()
    slots = db.query(TimeSlot).order_by(TimeSlot.order).all()

    slots_data = [
        {
            "id": s.id,
            "label": s.label,
            "start_time": str(s.start_time),
            "end_time": str(s.end_time),
            "order": s.order,
        }
        for s in slots
    ]

    return {
        "blocks": [{"id": b.id, "name": b.name, "description": b.description} for b in blocks],
        "departments": [{"id": d.id, "name": d.name, "code": d.code} for d in departments],
        "facilities": [{"id": f.id, "name": f.name} for f in facilities],
        "slots": slots_data,
        "time_slots": slots_data,
    }


def get_public_stats(db: Session) -> Dict[str, Any]:
    """Retrieve real-time aggregate statistics for public display."""
    today = date.today()
    total_rooms = db.query(Room).filter(Room.status == RoomStatus.ACTIVE).count()
    total_blocks = db.query(Block).count()
    bookings_today = (
        db.query(Booking)
        .filter(
            or_(
                Booking.date == today,
                func.date(Booking.created_at) == today,
            ),
            Booking.status != BookingStatus.CANCELLED,
            Booking.status != BookingStatus.REJECTED,
        )
        .count()
    )
    departments_count = db.query(Department).count()

    return {
        "total_rooms": total_rooms,
        "total_blocks": total_blocks,
        "bookings_today": bookings_today,
        "departments_count": departments_count,
    }

