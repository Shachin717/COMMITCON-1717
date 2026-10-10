import csv
from datetime import date, timedelta
import io
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.department import Department
from app.models.enums import BookingStatus, RoomStatus, RoomType
from app.models.room import Room
from app.models.time_slot import TimeSlot
from app.models.timetable import TimetableEntry
from app.models.user import User
from app.schemas.booking import BookingResponse
from app.schemas.hod import (
    HodDecisionRequest,
    HodLabResponse,
    HodPendingApprovalsResponse,
    HodRoomOption,
    HodSummaryResponse,
    HodUpcomingBooking,
)
from app.schemas.overview import DailyBookingStats, RoomTypeUsageStats
from app.services.audit import log_audit
from app.services.email import send_booking_approved_email, send_booking_rejected_email


def list_hod_bookings_history(
    db: Session,
    user: User,
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[BookingStatus] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    room_id: Optional[int] = None,
    student: Optional[str] = None,
    room_type: Optional[RoomType] = None,
    search: Optional[str] = None,
) -> Tuple[List[Booking], int]:
    """Retrieve bookings history of the HOD's department."""
    if not user.department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HOD is not assigned to any department.",
        )

    dept_id = user.department_id
    query = (
        db.query(Booking)
        .join(Room, Booking.room_id == Room.id)
        .options(
            joinedload(Booking.room).joinedload(Room.block),
            joinedload(Booking.slot),
            joinedload(Booking.department),
        )
        .filter(
            or_(
                Booking.department_id == dept_id,
                Room.department_id == dept_id,
            )
        )
    )

    if status_filter:
        query = query.filter(Booking.status == status_filter)
    if date_from:
        query = query.filter(Booking.date >= date_from)
    if date_to:
        query = query.filter(Booking.date <= date_to)
    if room_id:
        query = query.filter(Booking.room_id == room_id)
    if room_type:
        query = query.filter(Room.room_type == room_type)
    if student:
        student_pattern = f"%{student.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Booking.name).ilike(student_pattern),
                func.lower(Booking.roll_no).ilike(student_pattern),
                func.lower(Booking.email).ilike(student_pattern),
            )
        )
    if search:
        search_pattern = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Booking.reference).ilike(search_pattern),
                func.lower(Booking.name).ilike(search_pattern),
                func.lower(Booking.email).ilike(search_pattern),
                func.lower(Booking.roll_no).ilike(search_pattern),
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
    return bookings, total


def export_hod_bookings_csv(
    db: Session,
    user: User,
    status_filter: Optional[BookingStatus] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    room_id: Optional[int] = None,
    student: Optional[str] = None,
    room_type: Optional[RoomType] = None,
    search: Optional[str] = None,
) -> str:
    """Export all matching bookings history for HOD department as a CSV string."""
    if not user.department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HOD is not assigned to any department.",
        )

    dept_id = user.department_id
    query = (
        db.query(Booking)
        .join(Room, Booking.room_id == Room.id)
        .options(
            joinedload(Booking.room).joinedload(Room.block),
            joinedload(Booking.slot),
            joinedload(Booking.department),
        )
        .filter(
            or_(
                Booking.department_id == dept_id,
                Room.department_id == dept_id,
            )
        )
    )

    if status_filter:
        query = query.filter(Booking.status == status_filter)
    if date_from:
        query = query.filter(Booking.date >= date_from)
    if date_to:
        query = query.filter(Booking.date <= date_to)
    if room_id:
        query = query.filter(Booking.room_id == room_id)
    if room_type:
        query = query.filter(Room.room_type == room_type)
    if student:
        student_pattern = f"%{student.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Booking.name).ilike(student_pattern),
                func.lower(Booking.roll_no).ilike(student_pattern),
                func.lower(Booking.email).ilike(student_pattern),
            )
        )
    if search:
        search_pattern = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Booking.reference).ilike(search_pattern),
                func.lower(Booking.name).ilike(search_pattern),
                func.lower(Booking.email).ilike(search_pattern),
                func.lower(Booking.roll_no).ilike(search_pattern),
                func.lower(Booking.purpose).ilike(search_pattern),
            )
        )

    bookings = query.order_by(Booking.date.desc(), Booking.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Reference",
        "Date",
        "Slot",
        "Start Time",
        "End Time",
        "Room",
        "Block",
        "Floor",
        "Room Type",
        "Requester Name",
        "Roll No",
        "Email",
        "Requester Type",
        "Purpose",
        "Expected Strength",
        "Status",
        "Decision Note",
        "Created At",
    ])

    for b in bookings:
        room_name = b.room.name if b.room else ""
        block_name = b.room.block.name if (b.room and b.room.block) else ""
        floor = b.room.floor if b.room else ""
        room_type_str = b.room.room_type.value if b.room else ""
        slot_label = b.slot.label if b.slot else ""
        start_time_str = str(b.slot.start_time) if b.slot else ""
        end_time_str = str(b.slot.end_time) if b.slot else ""

        writer.writerow([
            b.reference,
            str(b.date),
            slot_label,
            start_time_str,
            end_time_str,
            room_name,
            block_name,
            floor,
            room_type_str,
            b.name,
            b.roll_no or "",
            b.email,
            b.requester_type.value if b.requester_type else "",
            b.purpose,
            b.expected_strength,
            b.status.value,
            b.decision_note or "",
            b.created_at.isoformat() if b.created_at else "",
        ])

    return output.getvalue()


def get_hod_department_summary(
    db: Session,
    user: User,
) -> HodSummaryResponse:
    """Retrieve departmental utilization summary, room metrics, and activity charts."""
    if not user.department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HOD is not assigned to any department.",
        )

    dept = db.query(Department).filter(Department.id == user.department_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found.",
        )

    dept_id = dept.id
    today = date.today()

    total_rooms = db.query(Room).filter(Room.department_id == dept_id).count()
    total_labs = (
        db.query(Room)
        .filter(Room.department_id == dept_id, Room.room_type == RoomType.LAB)
        .count()
    )
    active_rooms = (
        db.query(Room)
        .filter(Room.department_id == dept_id, Room.status == RoomStatus.ACTIVE)
        .count()
    )

    slots_count = db.query(TimeSlot).count() or 6
    daily_capacity = active_rooms * slots_count

    # Bookings today for department
    bookings_today = (
        db.query(Booking)
        .join(Room, Booking.room_id == Room.id)
        .filter(
            Booking.date == today,
            or_(Booking.department_id == dept_id, Room.department_id == dept_id),
        )
        .count()
    )

    # Active/confirmed room occupancies today in department rooms
    occupied_bookings_today = (
        db.query(Booking)
        .join(Room, Booking.room_id == Room.id)
        .filter(
            Booking.date == today,
            Room.department_id == dept_id,
            Booking.status.in_([
                BookingStatus.APPROVED,
                BookingStatus.COORDINATOR_APPROVED,
            ]),
        )
        .count()
    )

    weekday = today.weekday()
    timetable_occupied_today = (
        db.query(TimetableEntry)
        .join(Room, TimetableEntry.room_id == Room.id)
        .filter(
            TimetableEntry.day_of_week == weekday,
            Room.department_id == dept_id,
        )
        .count()
    )

    total_occupied_today = occupied_bookings_today + timetable_occupied_today
    if daily_capacity > 0:
        utilization_rate = round(min(100.0, (total_occupied_today / daily_capacity) * 100), 1)
    else:
        utilization_rate = 0.0

    # Pending approvals count
    pending_approvals_count = 0
    if dept.hod_approval_required:
        pending_approvals_count = (
            db.query(Booking)
            .join(Room, Booking.room_id == Room.id)
            .filter(
                Booking.status == BookingStatus.COORDINATOR_APPROVED,
                Booking.requires_hod_approval == True,
                Room.room_type.in_([RoomType.LAB, RoomType.EXAM_HALL]),
                or_(Room.department_id == dept_id, Booking.department_id == dept_id),
            )
            .count()
        )

    # Daily booking stats for the past 7 days
    bookings_per_day: List[DailyBookingStats] = []
    for i in range(6, -1, -1):
        target_d = today - timedelta(days=i)
        day_bookings = (
            db.query(Booking)
            .join(Room, Booking.room_id == Room.id)
            .filter(
                Booking.date == target_d,
                or_(Booking.department_id == dept_id, Room.department_id == dept_id),
            )
            .all()
        )
        confirmed = sum(
            1 for b in day_bookings
            if b.status in [BookingStatus.APPROVED, BookingStatus.COORDINATOR_APPROVED]
        )
        pending = sum(1 for b in day_bookings if b.status == BookingStatus.PENDING)
        rejected = sum(
            1 for b in day_bookings
            if b.status in [BookingStatus.REJECTED, BookingStatus.CANCELLED]
        )
        bookings_per_day.append(
            DailyBookingStats(
                date=target_d.isoformat(),
                day=target_d.strftime("%a"),
                total=len(day_bookings),
                confirmed=confirmed,
                pending=pending,
                rejected=rejected,
            )
        )

    # Room type usage distribution
    room_types = [
        (RoomType.LAB, "Laboratories"),
        (RoomType.CLASSROOM, "Classrooms"),
        (RoomType.EXAM_HALL, "Exam Halls"),
        (RoomType.SEMINAR_HALL, "Seminar Halls"),
    ]
    room_type_usage: List[RoomTypeUsageStats] = []
    for rt, label in room_types:
        r_count = (
            db.query(Room)
            .filter(Room.department_id == dept_id, Room.room_type == rt)
            .count()
        )
        b_count = (
            db.query(Booking)
            .join(Room, Booking.room_id == Room.id)
            .filter(
                Room.room_type == rt,
                or_(Booking.department_id == dept_id, Room.department_id == dept_id),
            )
            .count()
        )
        room_type_usage.append(
            RoomTypeUsageStats(
                room_type=rt.value,
                label=label,
                room_count=r_count,
                booking_count=b_count,
            )
        )

    # Recent bookings
    recent_raw = (
        db.query(Booking)
        .join(Room, Booking.room_id == Room.id)
        .options(
            joinedload(Booking.room).joinedload(Room.block),
            joinedload(Booking.slot),
            joinedload(Booking.department),
        )
        .filter(
            or_(Booking.department_id == dept_id, Room.department_id == dept_id)
        )
        .order_by(Booking.created_at.desc())
        .limit(5)
        .all()
    )
    recent_bookings = [BookingResponse.model_validate(b) for b in recent_raw]

    return HodSummaryResponse(
        department_id=dept.id,
        department_name=dept.name,
        department_code=dept.code,
        hod_approval_required=dept.hod_approval_required,
        total_rooms=total_rooms,
        total_labs=total_labs,
        bookings_today=bookings_today,
        pending_approvals_count=pending_approvals_count,
        utilization_rate=utilization_rate,
        bookings_per_day=bookings_per_day,
        room_type_usage=room_type_usage,
        recent_bookings=recent_bookings,
    )


def list_hod_department_labs(
    db: Session,
    user: User,
) -> List[HodLabResponse]:
    """Retrieve list of labs owned by the department with upcoming usage."""
    if not user.department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HOD is not assigned to any department.",
        )

    dept_id = user.department_id
    today = date.today()

    labs = (
        db.query(Room)
        .options(joinedload(Room.block), joinedload(Room.facilities))
        .filter(Room.department_id == dept_id, Room.room_type == RoomType.LAB)
        .order_by(Room.name.asc())
        .all()
    )

    slots_count = db.query(TimeSlot).count() or 6
    lab_responses: List[HodLabResponse] = []

    for lab in labs:
        # Upcoming bookings for this lab (today onwards, approved or coordinator approved)
        upcoming_raw = (
            db.query(Booking)
            .options(joinedload(Booking.slot))
            .filter(
                Booking.room_id == lab.id,
                Booking.date >= today,
                Booking.status.in_([
                    BookingStatus.APPROVED,
                    BookingStatus.COORDINATOR_APPROVED,
                ]),
            )
            .order_by(Booking.date.asc(), Booking.slot_id.asc())
            .limit(10)
            .all()
        )

        upcoming_list: List[HodUpcomingBooking] = []
        for ub in upcoming_raw:
            slot_label = ub.slot.label if ub.slot else "Scheduled Slot"
            start_str = str(ub.slot.start_time) if ub.slot else "09:00"
            end_str = str(ub.slot.end_time) if ub.slot else "10:00"
            upcoming_list.append(
                HodUpcomingBooking(
                    id=ub.id,
                    reference=ub.reference,
                    date=ub.date,
                    slot_label=slot_label,
                    start_time=start_str,
                    end_time=end_str,
                    purpose=ub.purpose,
                    requester_name=ub.name,
                    roll_no=ub.roll_no,
                    expected_strength=ub.expected_strength,
                    status=ub.status.value,
                )
            )

        total_bookings = db.query(Booking).filter(Booking.room_id == lab.id).count()
        today_bookings_count = (
            db.query(Booking)
            .filter(
                Booking.room_id == lab.id,
                Booking.date == today,
                Booking.status.in_([
                    BookingStatus.APPROVED,
                    BookingStatus.COORDINATOR_APPROVED,
                ]),
            )
            .count()
        )

        lab_utilization = (
            round(min(100.0, (today_bookings_count / slots_count) * 100), 1)
            if slots_count > 0
            else 0.0
        )

        facilities_list = [f.name for f in lab.facilities] if lab.facilities else []
        block_name = lab.block.name if lab.block else "Main Block"

        lab_responses.append(
            HodLabResponse(
                id=lab.id,
                name=lab.name,
                block_name=block_name,
                floor=lab.floor,
                capacity=lab.capacity,
                status=lab.status.value,
                maintenance_note=lab.maintenance_note,
                facilities=facilities_list,
                total_bookings=total_bookings,
                upcoming_bookings=upcoming_list,
                today_bookings_count=today_bookings_count,
                utilization_rate=lab_utilization,
            )
        )

    return lab_responses


def list_hod_department_rooms(
    db: Session,
    user: User,
) -> List[HodRoomOption]:
    """Retrieve list of rooms affiliated with the department for filtering."""
    if not user.department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HOD is not assigned to any department.",
        )

    dept_id = user.department_id
    rooms = (
        db.query(Room)
        .options(joinedload(Room.block))
        .filter(
            or_(
                Room.department_id == dept_id,
                Room.id.in_(
                    db.query(Booking.room_id).filter(Booking.department_id == dept_id)
                ),
            )
        )
        .order_by(Room.name.asc())
        .all()
    )

    return [
        HodRoomOption(
            id=r.id,
            name=r.name,
            room_type=r.room_type.value,
            block_name=r.block.name if r.block else "",
            capacity=r.capacity,
        )
        for r in rooms
    ]


def get_hod_pending_approvals(
    db: Session,
    user: User,
) -> HodPendingApprovalsResponse:
    """Retrieve pending approvals for LAB / EXAM_HALL bookings for the HOD's department."""
    if not user.department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HOD is not assigned to any department.",
        )

    dept = db.query(Department).filter(Department.id == user.department_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found.",
        )

    if not dept.hod_approval_required:
        return HodPendingApprovalsResponse(
            hod_approval_required=False,
            pending_bookings=[],
            message="HOD approval requirement is currently disabled for this department.",
        )

    dept_id = dept.id
    bookings = (
        db.query(Booking)
        .join(Room, Booking.room_id == Room.id)
        .options(
            joinedload(Booking.room).joinedload(Room.block),
            joinedload(Booking.slot),
            joinedload(Booking.department),
        )
        .filter(
            Booking.status == BookingStatus.COORDINATOR_APPROVED,
            Booking.requires_hod_approval == True,
            Room.room_type.in_([RoomType.LAB, RoomType.EXAM_HALL]),
            or_(
                Room.department_id == dept_id,
                Booking.department_id == dept_id,
            ),
        )
        .order_by(Booking.date.asc(), Booking.created_at.asc())
        .all()
    )

    return HodPendingApprovalsResponse(
        hod_approval_required=True,
        pending_bookings=[BookingResponse.model_validate(b) for b in bookings],
        message="Active pending HOD approvals retrieved.",
    )


def decide_hod_booking(
    db: Session,
    booking_id: int,
    user: User,
    decision_in: HodDecisionRequest,
) -> Booking:
    """HOD approves or rejects a COORDINATOR_APPROVED booking for their department."""
    if not user.department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HOD is not assigned to any department.",
        )

    dept = db.query(Department).filter(Department.id == user.department_id).first()
    if not dept or not dept.hod_approval_required:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HOD approval requirement is not active for this department.",
        )

    booking = (
        db.query(Booking)
        .options(
            joinedload(Booking.room).joinedload(Room.block),
            joinedload(Booking.slot),
            joinedload(Booking.department),
        )
        .filter(Booking.id == booking_id)
        .first()
    )
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with ID {booking_id} not found",
        )

    dept_id = user.department_id
    room_dept_id = booking.room.department_id if booking.room else None
    if booking.department_id != dept_id and room_dept_id != dept_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: This booking does not belong to your department.",
        )

    if booking.status != BookingStatus.COORDINATOR_APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot decide booking in status '{booking.status.value}'. Booking must be in COORDINATOR_APPROVED status.",
        )

    prev_status = booking.status.value
    action = decision_in.action.lower()

    if action == "approve":
        booking.status = BookingStatus.APPROVED
        booking.decision_note = (
            f"{booking.decision_note}; HOD: {decision_in.note}"
            if booking.decision_note and decision_in.note
            else (decision_in.note or booking.decision_note)
        )
        booking.decided_by = user.id
        audit_action = "BOOKING_HOD_APPROVED"

        slot_label = booking.slot.label if booking.slot else "Scheduled Slot"
        start_time_str = str(booking.slot.start_time) if booking.slot else "09:00"
        end_time_str = str(booking.slot.end_time) if booking.slot else "10:00"
        room_name = booking.room.name if booking.room else "Room"
        block_name = booking.room.block.name if (booking.room and booking.room.block) else "Campus Block"

        send_booking_approved_email(
            to_email=booking.email,
            reference=booking.reference,
            student_name=booking.name,
            room_name=room_name,
            block_name=block_name,
            date_str=str(booking.date),
            slot_label=slot_label,
            start_time_str=start_time_str,
            end_time_str=end_time_str,
            purpose=booking.purpose,
            decision_note=decision_in.note,
        )

    elif action == "reject":
        booking.status = BookingStatus.REJECTED
        booking.decision_note = (
            f"{booking.decision_note}; HOD Rejected: {decision_in.note}"
            if booking.decision_note and decision_in.note
            else (decision_in.note or "Rejected by Department HOD")
        )
        booking.decided_by = user.id
        audit_action = "BOOKING_HOD_REJECTED"

        slot_label = booking.slot.label if booking.slot else "Scheduled Slot"
        room_name = booking.room.name if booking.room else "Room"

        send_booking_rejected_email(
            to_email=booking.email,
            reference=booking.reference,
            student_name=booking.name,
            room_name=room_name,
            date_str=str(booking.date),
            slot_label=slot_label,
            rejection_reason=decision_in.note or "Rejected by Department HOD",
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid action. Must be 'approve' or 'reject'.",
        )

    db.commit()
    db.refresh(booking)

    log_audit(
        db,
        action=audit_action,
        entity="Booking",
        entity_id=booking.id,
        actor_id=user.id,
        meta={
            "reference": booking.reference,
            "previous_status": prev_status,
            "new_status": booking.status.value,
            "action": action,
            "note": decision_in.note,
        },
    )

    return booking
