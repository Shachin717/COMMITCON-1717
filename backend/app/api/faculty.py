from datetime import date, datetime, timezone
import math
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.booking import Booking
from app.models.department import Department
from app.models.enums import BookingStatus, RequesterType, RoomType, UserRole
from app.models.room import Room
from app.models.time_slot import TimeSlot
from app.models.user import User
from app.schemas.booking import BookingResponse
from app.schemas.common import PaginatedResponse
from app.schemas.faculty import (
    FacultyBookingCreate,
    FacultyCancelResponse,
    FacultyPendingCountResponse,
)
from app.schemas.public import AvailabilityResponse
from app.services.audit import log_audit
from app.services.email import (
    send_booking_acknowledgement_email,
    send_booking_cancellation_email,
)
from app.services.public import (
    check_room_availability,
    generate_secure_token,
    generate_unique_reference,
    hash_token,
    query_availability,
)

router = APIRouter(
    prefix="/faculty",
    tags=["Faculty"],
    dependencies=[Depends(require_roles(UserRole.FACULTY))],
)


def _parse_int_list(val: Optional[str]) -> List[int]:
    """Parse comma-separated integers or single integer string."""
    if not val or not val.strip():
        return []
    result = []
    for part in val.split(","):
        part = part.strip()
        if part.isdigit():
            result.append(int(part))
    return result


def _parse_str_list(val: Optional[str]) -> List[str]:
    """Parse comma-separated strings."""
    if not val or not val.strip():
        return []
    return [p.strip() for p in val.split(",") if p.strip()]


@router.get(
    "/availability",
    response_model=AvailabilityResponse,
    summary="Query available rooms for faculty",
)
def get_faculty_availability(
    request: Request,
    date: date = Query(..., description="Target allocation date (YYYY-MM-DD)"),
    slot_ids: Optional[str] = Query(None, description="Comma-separated time slot IDs"),
    min_capacity: Optional[int] = Query(None, description="Minimum seating capacity"),
    facilities: Optional[str] = Query(None, description="Comma-separated required facilities"),
    room_type: Optional[RoomType] = Query(None, description="Room category filter"),
    block_id: Optional[int] = Query(None, description="Physical building/block ID"),
    department_id: Optional[int] = Query(None, description="Department ID filter"),
    current_user: User = Depends(require_roles(UserRole.FACULTY)),
    db: Session = Depends(get_db),
):
    parsed_slots = _parse_int_list(slot_ids)
    parsed_facilities = _parse_str_list(facilities)

    available_rooms, suggestions = query_availability(
        db=db,
        target_date=date,
        slot_ids=parsed_slots,
        min_capacity=min_capacity,
        facilities=parsed_facilities,
        room_type=room_type,
        block_id=block_id,
        department_id=department_id,
    )

    return AvailabilityResponse(
        date=date,
        slot_ids=parsed_slots,
        total_available=len(available_rooms),
        available_rooms=available_rooms,
        suggestions=suggestions,
    )


@router.get(
    "/bookings",
    response_model=PaginatedResponse[BookingResponse],
    summary="Get my bookings as faculty",
)
def get_faculty_bookings(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    status: Optional[BookingStatus] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search keyword"),
    current_user: User = Depends(require_roles(UserRole.FACULTY)),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Booking)
        .options(
            joinedload(Booking.room).joinedload(Room.block),
            joinedload(Booking.slot),
            joinedload(Booking.department),
        )
        .filter(Booking.email == current_user.email.lower().strip())
    )

    if status:
        query = query.filter(Booking.status == status)

    if search:
        search_pattern = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Booking.reference).ilike(search_pattern),
                func.lower(Booking.purpose).ilike(search_pattern),
            )
        )

    total = query.count()
    bookings = (
        query.order_by(Booking.date.desc(), Booking.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    pages = math.ceil(total / page_size) if page_size > 0 else 0

    return PaginatedResponse(
        items=[BookingResponse.model_validate(b) for b in bookings],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/bookings/pending-count",
    response_model=FacultyPendingCountResponse,
    summary="Get count of pending/active bookings for real-time polling badge",
)
def get_faculty_pending_count(
    current_user: User = Depends(require_roles(UserRole.FACULTY)),
    db: Session = Depends(get_db),
):
    pending_count = (
        db.query(Booking)
        .filter(
            Booking.email == current_user.email.lower().strip(),
            Booking.status.in_([BookingStatus.PENDING, BookingStatus.COORDINATOR_APPROVED]),
        )
        .count()
    )
    total_count = (
        db.query(Booking)
        .filter(Booking.email == current_user.email.lower().strip())
        .count()
    )
    return FacultyPendingCountResponse(
        pending_count=pending_count,
        total_bookings=total_count,
    )


@router.post(
    "/bookings",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit room booking request as authenticated faculty",
)
def create_faculty_booking(
    data: FacultyBookingCreate,
    current_user: User = Depends(require_roles(UserRole.FACULTY)),
    db: Session = Depends(get_db),
):
    if data.date < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot book a room for a past date.",
        )

    room = (
        db.query(Room)
        .options(joinedload(Room.department), joinedload(Room.block))
        .filter(Room.id == data.room_id)
        .first()
    )
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specified room does not exist.")

    slot = db.query(TimeSlot).filter(TimeSlot.id == data.slot_id).first()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specified time slot does not exist.")

    if data.expected_strength > room.capacity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expected strength ({data.expected_strength}) exceeds room capacity ({room.capacity}).",
        )

    # Check availability
    is_avail, conflict_reason = check_room_availability(db, room, data.date, [data.slot_id])
    if not is_avail:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=conflict_reason or "The selected room and slot is not available.",
        )

    # Department assignment
    dept_id = current_user.department_id or room.department_id
    if not dept_id:
        dept = db.query(Department).first()
        dept_id = dept.id if dept else 1

    dept_obj = db.query(Department).filter(Department.id == dept_id).first()

    # Determine HOD approval requirement
    requires_hod = False
    if room.room_type in (RoomType.LAB, RoomType.EXAM_HALL):
        check_dept = room.department or dept_obj
        if check_dept and check_dept.hod_approval_required:
            requires_hod = True

    reference = generate_unique_reference(db)
    raw_cancel_token = generate_secure_token(32)
    cancel_hash = hash_token(raw_cancel_token)

    booking = Booking(
        reference=reference,
        room_id=room.id,
        date=data.date,
        slot_id=slot.id,
        purpose=data.purpose.strip(),
        expected_strength=data.expected_strength,
        required_facilities=data.required_facilities,
        status=BookingStatus.PENDING,
        requires_hod_approval=requires_hod,
        requester_type=RequesterType.FACULTY,
        roll_no=data.faculty_id or f"FAC-{current_user.id}",
        name=current_user.name.strip(),
        department_id=dept_id,
        class_name=data.class_name or "Academic Session",
        phone=data.phone or current_user.phone or "N/A",
        email=current_user.email.strip().lower(),
        cancel_token_hash=cancel_hash,
    )

    db.add(booking)
    db.commit()
    db.refresh(booking)

    log_audit(
        db,
        action="BOOKING_CREATED_FACULTY",
        entity="Booking",
        entity_id=booking.id,
        actor_id=current_user.id,
        meta={"reference": booking.reference, "room_id": room.id, "date": str(data.date)},
    )

    try:
        send_booking_acknowledgement_email(
            to_email=booking.email,
            reference=booking.reference,
            student_name=booking.name,
            room_name=room.name,
            date_str=str(booking.date),
            slot_label=slot.label,
            cancel_token=raw_cancel_token,
        )
    except Exception:
        pass


    return BookingResponse.model_validate(booking)


@router.post(
    "/bookings/{booking_id}/cancel",
    response_model=FacultyCancelResponse,
    summary="Cancel my booking as faculty",
)
def cancel_faculty_booking(
    booking_id: int,
    current_user: User = Depends(require_roles(UserRole.FACULTY)),
    db: Session = Depends(get_db),
):
    booking = (
        db.query(Booking)
        .options(
            joinedload(Booking.room).joinedload(Room.block),
            joinedload(Booking.slot),
        )
        .filter(Booking.id == booking_id)
        .first()
    )
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with ID {booking_id} not found.",
        )

    if booking.email.lower().strip() != current_user.email.lower().strip() and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You can only cancel your own bookings.",
        )

    if booking.status in (BookingStatus.CANCELLED, BookingStatus.REJECTED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Booking is already in status {booking.status.value}.",
        )

    booking.status = BookingStatus.CANCELLED
    booking.decision_note = f"Cancelled by faculty member ({current_user.name})"
    db.commit()

    log_audit(
        db,
        action="BOOKING_CANCELLED_FACULTY",
        entity="Booking",
        entity_id=booking.id,
        actor_id=current_user.id,
        meta={"reference": booking.reference},
    )

    slot_label = booking.slot.label if booking.slot else f"Slot {booking.slot_id}"
    room_name = booking.room.name if booking.room else "Room"

    try:
        send_booking_cancellation_email(
            to_email=booking.email,
            reference=booking.reference,
            student_name=booking.name,
            room_name=room_name,
            date_str=str(booking.date),
            slot_label=slot_label,
        )
    except Exception:
        pass


    return FacultyCancelResponse(
        message="Booking has been successfully cancelled and the room slot is freed.",
        reference=booking.reference,
        status="CANCELLED",
        cancelled_at=datetime.now(timezone.utc),
    )
