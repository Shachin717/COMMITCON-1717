from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.booking import Booking
from app.models.enums import BookingStatus, RoomType
from app.services.audit import log_audit
from app.schemas.public import (
    AvailabilityResponse,
    CancelOtpRequest,
    CancelResponse,
    PublicBookingCancelRequest,
    PublicBookingCreate,
    PublicBookingResponse,
    PublicBookingStatusResponse,
    TimetableResponse,
    WaitlistCreate,
    WaitlistResponse,
)
from app.services.public import (
    AvailabilityConflictException,
    cancel_booking,
    create_public_booking,
    get_booking_by_reference_and_email,
    get_public_metadata,
    get_public_stats,
    get_public_timetable,
    join_waitlist,
    query_availability,
    request_cancellation_otp,
)

public_router = APIRouter()


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


@public_router.get(
    "/availability",
    response_model=AvailabilityResponse,
    summary="Query available rooms for a given date and slot",
)
@limiter.limit(settings.PUBLIC_RATE_LIMIT)
def get_availability(
    request: Request,
    date: date = Query(..., description="Target allocation date (YYYY-MM-DD)"),
    slot_ids: Optional[str] = Query(None, description="Comma-separated time slot IDs"),
    min_capacity: Optional[int] = Query(None, description="Minimum seating capacity"),
    facilities: Optional[str] = Query(None, description="Comma-separated required facilities"),
    room_type: Optional[RoomType] = Query(None, description="Room category filter"),
    block_id: Optional[int] = Query(None, description="Physical building/block ID"),
    department_id: Optional[int] = Query(None, description="Department ID filter"),
    db: Session = Depends(get_db),
):
    """
    Search available rooms. A room is available if it is ACTIVE, has no RoomBlock for that date/slot,
    no TimetableEntry for that weekday/slot, and no active booking.
    Rooms are ranked by fit score (best-fit capacity first, then facility match).
    If nothing is available, suggestions for nearest free slots and alternative rooms are returned.
    """
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


@public_router.get(
    "/timetable",
    response_model=TimetableResponse,
    summary="Retrieve full room x slot timetable grid",
)
@limiter.limit(settings.PUBLIC_RATE_LIMIT)
def get_timetable(
    request: Request,
    response: Response,
    date: date = Query(..., description="Target schedule date (YYYY-MM-DD)"),
    block_id: Optional[int] = Query(None, description="Optional building/block ID filter"),
    db: Session = Depends(get_db),
):
    """
    Returns a grid (rooms x slots) showing FREE / BOOKED / CLASS / MAINTENANCE / EXAM per cell.
    Cached for a few seconds to reduce database pressure.
    """
    response.headers["Cache-Control"] = "public, max-age=10, stale-while-revalidate=5"
    return get_public_timetable(db=db, target_date=date, block_id=block_id)


@public_router.post(
    "/bookings",
    response_model=PublicBookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit student room booking request",
)
@limiter.limit(settings.PUBLIC_BOOKING_RATE_LIMIT)
def submit_booking(
    request: Request,
    booking_in: PublicBookingCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Validates student details, performs atomic availability check inside transaction,
    handles DB exclusion constraint gracefully with 409 and suggested alternatives, creates
    booking as PENDING, generates reference code and secure cancel token hash, and sends acknowledgement email in background.
    """
    try:
        booking, cancel_token = create_public_booking(
            db=db,
            booking_in=booking_in,
            background_tasks=background_tasks,
        )
        return PublicBookingResponse(
            id=booking.id,
            reference=booking.reference,
            cancel_token=cancel_token,
            status=booking.status,
            room_id=booking.room_id,
            room_name=booking.room.name if booking.room else "",
            date=booking.date,
            slot_id=booking.slot_id,
            slot_label=booking.slot.label if booking.slot else "",
            roll_no=booking.roll_no or "",
            name=booking.name,
            email=booking.email,
            department_id=booking.department_id,
            department_name=booking.department.name if booking.department else None,
            class_name=booking.class_name or "",
            phone=booking.phone,
            purpose=booking.purpose,
            expected_strength=booking.expected_strength,
            required_facilities=booking.required_facilities or [],
            requires_hod_approval=booking.requires_hod_approval,
            created_at=booking.created_at,
            message="Booking request submitted successfully. Check your email for reference and cancellation link.",
        )
    except AvailabilityConflictException as ace:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=ace.detail,
        )


@public_router.get(
    "/bookings/{reference}",
    response_model=PublicBookingStatusResponse,
    summary="Lookup booking status by reference code and email",
)
@limiter.limit(settings.PUBLIC_RATE_LIMIT)
def get_booking_status(
    request: Request,
    reference: str,
    email: str = Query(..., description="Student email used for booking"),
    db: Session = Depends(get_db),
):
    """
    Public booking status lookup using Booking Reference + matching student email.
    """
    booking = get_booking_by_reference_and_email(db=db, reference=reference, email=email)
    return PublicBookingStatusResponse(
        reference=booking.reference,
        status=booking.status,
        room_id=booking.room_id,
        room_name=booking.room.name if booking.room else "",
        block_name=booking.room.block.name if (booking.room and booking.room.block) else None,
        floor=booking.room.floor if booking.room else None,
        date=booking.date,
        slot_id=booking.slot_id,
        slot_label=booking.slot.label if booking.slot else "",
        roll_no=booking.roll_no,
        name=booking.name,
        email=booking.email,
        phone=booking.phone,
        department_name=booking.department.name if booking.department else None,
        class_name=booking.class_name,
        purpose=booking.purpose,
        expected_strength=booking.expected_strength,
        required_facilities=booking.required_facilities or [],
        requires_hod_approval=booking.requires_hod_approval,
        decision_note=booking.decision_note,
        checked_in=getattr(booking, "checked_in", False),
        created_at=booking.created_at,
    )


@public_router.post(
    "/bookings/{reference}/check-in",
    summary="Check in to an approved booking to confirm arrival and prevent auto-release",
)
@limiter.limit(settings.PUBLIC_BOOKING_RATE_LIMIT)
def check_in_booking(
    request: Request,
    reference: str,
    db: Session = Depends(get_db),
):
    """
    Mark attendance/check-in for an approved booking slot, preventing no-show auto-release.
    """
    booking = db.query(Booking).filter(Booking.reference == reference.strip()).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
    if booking.status != BookingStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only APPROVED bookings can be checked in. Current status: {booking.status.value}",
        )
    if booking.checked_in:
        return {"message": "Booking is already checked in.", "reference": booking.reference, "checked_in": True}

    booking.checked_in = True
    db.commit()
    log_audit(
        db=db,
        action="BOOKING_CHECKED_IN",
        entity="Booking",
        entity_id=booking.id,
        actor_id=None,
        meta={"reference": booking.reference, "date": str(booking.date), "room_id": booking.room_id},
    )
    return {"message": "Successfully checked in. Room reservation confirmed.", "reference": booking.reference, "checked_in": True}


@public_router.post(
    "/bookings/cancel/request-otp",
    summary="Request a 6-digit OTP code to cancel booking",
)
@limiter.limit(settings.PUBLIC_BOOKING_RATE_LIMIT)
def request_cancel_otp(
    request: Request,
    req_body: CancelOtpRequest,
    db: Session = Depends(get_db),
):
    """
    Generate and email a 6-digit verification code to the student for booking cancellation.
    """
    request_cancellation_otp(db=db, reference=req_body.reference, email=str(req_body.email))
    return {"message": "Cancellation OTP sent successfully to your email."}


@public_router.post(
    "/bookings/cancel",
    response_model=CancelResponse,
    summary="Cancel booking by cancel token or reference + email OTP",
)
@limiter.limit(settings.PUBLIC_BOOKING_RATE_LIMIT)
def cancel_public_booking(
    request: Request,
    cancel_req: PublicBookingCancelRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Cancel booking either via secure cancel token OR reference + email + OTP.
    Sets status to CANCELLED, frees the slot, writes AuditLog, dispatches cancellation email in background,
    and alerts the first waitlisted student in background.
    """
    booking = cancel_booking(db=db, cancel_req=cancel_req, background_tasks=background_tasks)
    return CancelResponse(
        message="Booking has been successfully cancelled and the room slot is freed.",
        reference=booking.reference,
        status="CANCELLED",
        cancelled_at=datetime.now(timezone.utc),
    )


@public_router.post(
    "/waitlist",
    response_model=WaitlistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Join waitlist for an occupied room and time slot",
)
@limiter.limit(settings.PUBLIC_BOOKING_RATE_LIMIT)
def join_room_waitlist(
    request: Request,
    waitlist_in: WaitlistCreate,
    db: Session = Depends(get_db),
):
    """
    Join waitlist when a room/slot is unavailable. When a current booking is cancelled,
    the system automatically dispatches an alert email to the first waitlisted user.
    """
    entry = join_waitlist(db=db, waitlist_in=waitlist_in)
    return WaitlistResponse(
        id=entry.id,
        room_id=entry.room_id,
        room_name=entry.room.name if entry.room else "",
        date=entry.date,
        slot_id=entry.slot_id,
        slot_label=entry.slot.label if entry.slot else "",
        message="You have been added to the waitlist. You will be notified via email if this slot becomes available.",
    )


@public_router.get(
    "/meta",
    summary="Retrieve dropdown and filter metadata (blocks, departments, facilities, time slots)",
)
@limiter.limit(settings.PUBLIC_RATE_LIMIT)
def get_metadata(
    request: Request,
    db: Session = Depends(get_db),
):
    """Returns blocks, departments, facilities, and time slots for public search and filter chips."""
    return get_public_metadata(db=db)


@public_router.get(
    "/stats",
    summary="Retrieve public metrics for display",
)
@limiter.limit(settings.PUBLIC_RATE_LIMIT)
def get_stats(
    request: Request,
    db: Session = Depends(get_db),
):
    """Returns live campus stats: total rooms, total blocks, bookings today."""
    return get_public_stats(db=db)


