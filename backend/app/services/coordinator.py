import csv
from datetime import date, datetime, timedelta, timezone
import io
import math
import threading
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.audit_log import AuditLog
from app.models.block import Block, BlockCoordinator
from app.models.booking import Booking
from app.models.enums import BookingStatus, RequesterType, RoomBlockReason, RoomStatus, RoomType, UserRole
from app.models.room import Room
from app.models.room_block import RoomBlock
from app.models.time_slot import TimeSlot
from app.models.timetable import TimetableEntry
from app.models.user import User
from app.models.waitlist import WaitlistEntry
from app.schemas.coordinator import (
    AffectedBookingItem,
    BlockOverviewResponse,
    BlockedRoomItem,
    BlockedRoomSummary,
    BlockedRoomsResponse,
    BlockedRoomsSummaryCounts,
    ConfirmRelocationRequest,
    ConfirmRelocationResponse,
    CoordinatorBulkDecisionRequest,
    CoordinatorBulkDecisionResponse,
    CoordinatorDecisionRequest,
    CoordinatorRoomBlockCreate,
    CoordinatorRoomBlockPreviewRequest,
    RoomBlockBatchResponse,
    RoomBlockBulkReleaseRequest,
    RoomBlockBulkReleaseResponse,
    RoomBlockPreviewResponse,
    RoomBlockReleaseResponse,
    RoomBlockSummary,
    RoomMaintenanceReleaseResponse,
    RoomOverviewItem,
)
from app.schemas.public import TimetableResponse
from app.services.audit import log_audit
from app.services.email import (
    send_booking_approved_email,
    send_booking_rejected_email,
    send_booking_relocated_email,
)
from app.services.public import clear_timetable_cache, get_public_timetable, _send_waitlist_email



def get_coordinator_block_ids(db: Session, user: User) -> List[int]:
    """Return list of block IDs assigned to the coordinator."""
    rows = (
        db.query(BlockCoordinator.block_id)
        .filter(BlockCoordinator.user_id == user.id)
        .all()
    )
    return [r[0] for r in rows]


def get_coordinator_blocks(db: Session, user: User) -> List[Block]:
    """Return blocks assigned to coordinator."""
    my_block_ids = get_coordinator_block_ids(db, user)
    if not my_block_ids:
        return []
    return (
        db.query(Block)
        .filter(Block.id.in_(my_block_ids))
        .order_by(Block.id.asc())
        .all()
    )


def get_coordinator_rooms(
    db: Session,
    user: User,
    block_id: Optional[int] = None,
    search: Optional[str] = None,
    status_filter: Optional[RoomStatus] = None,
) -> List[Room]:
    """Return rooms in coordinator's assigned blocks with optional block_id, search, and status filters."""
    my_block_ids = get_coordinator_block_ids(db, user)
    if not my_block_ids:
        return []

    if block_id is not None:
        if block_id not in my_block_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: Block is not assigned to you.",
            )
        target_block_ids = [block_id]
    else:
        target_block_ids = my_block_ids

    query = (
        db.query(Room)
        .options(joinedload(Room.block))
        .filter(Room.block_id.in_(target_block_ids))
    )

    if status_filter:
        query = query.filter(Room.status == status_filter)

    if search and search.strip():
        query = query.filter(Room.name.ilike(f"%{search.strip()}%"))

    return query.order_by(Room.block_id.asc(), Room.name.asc()).all()


def list_coordinator_bookings(
    db: Session,
    user: User,
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[BookingStatus] = None,
    only_pending: bool = False,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    room_id: Optional[int] = None,
    block_id: Optional[int] = None,
    search: Optional[str] = None,
) -> Tuple[List[Booking], int]:
    """Retrieve bookings for rooms in blocks assigned to the coordinator."""
    my_block_ids = get_coordinator_block_ids(db, user)
    if not my_block_ids:
        return [], 0

    query = (
        db.query(Booking)
        .join(Room, Booking.room_id == Room.id)
        .options(
            joinedload(Booking.room).joinedload(Room.block),
            joinedload(Booking.slot),
            joinedload(Booking.department),
        )
        .filter(Room.block_id.in_(my_block_ids))
    )

    if block_id:
        if block_id not in my_block_ids:
            return [], 0
        query = query.filter(Room.block_id == block_id)

    if only_pending:
        query = query.filter(Booking.status == BookingStatus.PENDING)
    elif status_filter:
        query = query.filter(Booking.status == status_filter)

    if date_from:
        query = query.filter(Booking.date >= date_from)
    if date_to:
        query = query.filter(Booking.date <= date_to)
    if room_id:
        query = query.filter(Booking.room_id == room_id)

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
        query.order_by(Booking.date.asc(), Booking.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return bookings, total


def decide_coordinator_booking(
    db: Session,
    booking_id: int,
    user: User,
    decision_in: CoordinatorDecisionRequest,
) -> Booking:
    """Coordinator approves or rejects a booking in their assigned blocks.

    State transition:
    - If action == 'approve':
        - If requires_hod_approval is True -> status becomes COORDINATOR_APPROVED
        - If requires_hod_approval is False -> status becomes APPROVED, send confirmation email + ICS
    - If action == 'reject':
        - status becomes REJECTED with note, send rejection email
    """
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

    my_block_ids = get_coordinator_block_ids(db, user)
    if booking.room.block_id not in my_block_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: This booking belongs to a block outside your coordinator assignment.",
        )

    if booking.status != BookingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot decide booking in status '{booking.status.value}'. Only PENDING bookings can be decided by coordinator.",
        )

    prev_status = booking.status.value
    action = decision_in.action.lower()

    if action == "approve":
        if booking.requires_hod_approval:
            booking.status = BookingStatus.COORDINATOR_APPROVED
            booking.decision_note = decision_in.note
            booking.decided_by = user.id
            audit_action = "BOOKING_COORDINATOR_APPROVED"
        else:
            booking.status = BookingStatus.APPROVED
            booking.decision_note = decision_in.note
            booking.decided_by = user.id
            audit_action = "BOOKING_APPROVED"

            # Dispatch confirmation email with ICS calendar
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
        if not decision_in.note or not decision_in.note.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rejection reason is required.",
            )
        booking.status = BookingStatus.REJECTED
        booking.decision_note = decision_in.note.strip()
        booking.decided_by = user.id
        audit_action = "BOOKING_REJECTED"

        # Dispatch rejection email
        slot_label = booking.slot.label if booking.slot else "Scheduled Slot"
        room_name = booking.room.name if booking.room else "Room"

        send_booking_rejected_email(
            to_email=booking.email,
            reference=booking.reference,
            student_name=booking.name,
            room_name=room_name,
            date_str=str(booking.date),
            slot_label=slot_label,
            rejection_reason=decision_in.note.strip(),
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
            "requires_hod_approval": booking.requires_hod_approval,
            "note": decision_in.note,
        },
    )

    return booking


def get_all_blocks_overview(
    db: Session,
    user: User,
    target_date: date,
    slot_id: Optional[int] = None,
) -> BlockOverviewResponse:
    """Overview of ALL blocks: booked rooms and remaining free rooms for a date/slot.

    Read-only across all blocks. Flags is_my_block for UI convenience.
    """
    my_block_ids = set(get_coordinator_block_ids(db, user))

    rooms = (
        db.query(Room)
        .options(joinedload(Room.block))
        .order_by(Room.block_id, Room.name)
        .all()
    )

    # Pre-fetch room blocks for date
    rb_query = db.query(RoomBlock).filter(
        RoomBlock.date == target_date,
        RoomBlock.is_released.is_(False),
    )
    if slot_id:
        rb_query = rb_query.filter(or_(RoomBlock.slot_id.is_(None), RoomBlock.slot_id == slot_id))
    room_blocks = rb_query.all()
    blocks_map = {(rb.room_id, rb.slot_id): rb for rb in room_blocks}
    full_day_blocks = {rb.room_id: rb for rb in room_blocks if rb.slot_id is None}

    # Pre-fetch timetable entries if slot_id given
    weekday = target_date.weekday()
    te_query = db.query(TimetableEntry).filter(TimetableEntry.day_of_week == weekday)
    if slot_id:
        te_query = te_query.filter(TimetableEntry.slot_id == slot_id)
    timetable_entries = te_query.all()
    timetable_map = {(te.room_id, te.slot_id): te for te in timetable_entries}

    # Pre-fetch active bookings
    b_query = (
        db.query(Booking)
        .filter(
            Booking.date == target_date,
            Booking.status.in_([
                BookingStatus.PENDING,
                BookingStatus.COORDINATOR_APPROVED,
                BookingStatus.APPROVED,
            ]),
        )
    )
    if slot_id:
        b_query = b_query.filter(Booking.slot_id == slot_id)
    active_bookings = b_query.all()
    bookings_map = {(b.room_id, b.slot_id): b for b in active_bookings}

    items: List[RoomOverviewItem] = []
    booked_count = 0
    free_count = 0
    other_count = 0

    for r in rooms:
        status_str = "FREE"
        b_ref = None
        purpose = None
        is_booked = False

        if r.status == RoomStatus.MAINTENANCE:
            status_str = "MAINTENANCE"
            other_count += 1
        elif r.id in full_day_blocks:
            rb = full_day_blocks[r.id]
            status_str = "EXAM" if rb.reason == RoomBlockReason.EXAM else "MAINTENANCE"
            other_count += 1
        elif slot_id and (r.id, slot_id) in blocks_map:
            rb = blocks_map[(r.id, slot_id)]
            status_str = "EXAM" if rb.reason == RoomBlockReason.EXAM else "MAINTENANCE"
            other_count += 1
        elif slot_id and (r.id, slot_id) in timetable_map:
            status_str = "CLASS"
            other_count += 1
        elif slot_id and (r.id, slot_id) in bookings_map:
            bk = bookings_map[(r.id, slot_id)]
            status_str = "BOOKED"
            is_booked = True
            b_ref = bk.reference
            purpose = bk.purpose
            booked_count += 1
        elif not slot_id:
            # When slot_id is None, check if room has any booking on that date
            room_bks = [b for b in active_bookings if b.room_id == r.id]
            if room_bks:
                status_str = "BOOKED"
                is_booked = True
                b_ref = room_bks[0].reference
                purpose = room_bks[0].purpose
                booked_count += 1
            else:
                free_count += 1
        else:
            status_str = "FREE"
            free_count += 1

        items.append(
            RoomOverviewItem(
                room_id=r.id,
                room_name=r.name,
                block_id=r.block_id,
                block_name=r.block.name if r.block else "",
                capacity=r.capacity,
                room_type=r.room_type,
                is_booked=is_booked,
                status=status_str,
                booking_reference=b_ref,
                purpose=purpose,
                is_my_block=r.block_id in my_block_ids,
            )
        )

    return BlockOverviewResponse(
        date=target_date,
        slot_id=slot_id,
        total_rooms=len(rooms),
        booked_rooms_count=booked_count,
        free_rooms_count=free_count,
        other_rooms_count=other_count,
        rooms=items,
    )


def create_coordinator_room_blocks(
    db: Session,
    user: User,
    data: CoordinatorRoomBlockCreate,
) -> RoomBlockBatchResponse:
    """Block a room for MAINTENANCE or EXAM (creating RoomBlock with date range and slots)

    and mark it as EXAM_HALL usage if requested. Restricted to coordinator's assigned blocks.
    """
    room = db.query(Room).options(joinedload(Room.block)).filter(Room.id == data.room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {data.room_id} not found",
        )

    my_block_ids = get_coordinator_block_ids(db, user)
    if room.block_id not in my_block_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You can only block rooms within your assigned blocks.",
        )

    if data.date_from > data.date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_from cannot be after date_to",
        )

    # If mark_as_exam_hall is True, update room_type to EXAM_HALL
    if data.mark_as_exam_hall:
        room.room_type = RoomType.EXAM_HALL
        db.add(room)

    # Generate dates in range
    curr = data.date_from
    created_blocks: List[RoomBlock] = []

    # Get slots if specified
    slot_ids = data.slot_ids if data.slot_ids else [None]

    while curr <= data.date_to:
        for s_id in slot_ids:
            # Check if an overlapping active room block already exists
            existing_query = (
                db.query(RoomBlock)
                .filter(
                    RoomBlock.room_id == room.id,
                    RoomBlock.date == curr,
                    RoomBlock.is_released.is_(False),
                )
            )
            if s_id is not None:
                existing_query = existing_query.filter(
                    or_(RoomBlock.slot_id.is_(None), RoomBlock.slot_id == s_id)
                )
            existing = existing_query.first()
            if existing:
                slot_lbl = existing.slot.label if existing.slot else "Full Day"
                reason_lbl = existing.reason.value if hasattr(existing.reason, "value") else str(existing.reason)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Room {room.name} is already blocked on {curr} ({slot_lbl}) for {reason_lbl}.",
                )
            rb = RoomBlock(
                room_id=room.id,
                date=curr,
                slot_id=s_id,
                reason=data.reason,
                note=data.note,
                created_by=user.id,
            )
            db.add(rb)
            created_blocks.append(rb)
        curr += timedelta(days=1)

    db.commit()
    clear_timetable_cache()

    for rb in created_blocks:
        db.refresh(rb)

    log_audit(
        db,
        action="ROOM_BLOCK_CREATED",
        entity="RoomBlock",
        entity_id=room.id,
        actor_id=user.id,
        meta={
            "room_id": room.id,
            "room_name": room.name,
            "reason": data.reason.value,
            "date_from": str(data.date_from),
            "date_to": str(data.date_to),
            "slots": data.slot_ids,
            "mark_as_exam_hall": data.mark_as_exam_hall,
            "blocks_count": len(created_blocks),
        },
    )

    summaries = [
        RoomBlockSummary(
            id=rb.id,
            room_id=rb.room_id,
            room_name=room.name,
            date=rb.date,
            slot_id=rb.slot_id,
            slot_label=rb.slot.label if rb.slot else "Full Day",
            reason=rb.reason,
            note=rb.note,
            created_by=rb.created_by,
        )
        for rb in created_blocks
    ]

    return RoomBlockBatchResponse(
        message=f"Successfully created {len(created_blocks)} room block records.",
        created_count=len(created_blocks),
        blocks=summaries,
    )


def get_coordinator_timetable(
    db: Session,
    user: User,
    target_date: date,
    block_id: Optional[int] = None,
) -> TimetableResponse:
    """Timetable (same shape as public timetable), restricted or filtered by coordinator's blocks if block_id not given."""
    my_block_ids = get_coordinator_block_ids(db, user)
    if block_id:
        if block_id not in my_block_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: Requested block is not assigned to you.",
            )
        target_block = block_id
    else:
        # Default to first assigned block if exists
        target_block = my_block_ids[0] if my_block_ids else None

    return get_public_timetable(db=db, target_date=target_date, block_id=target_block)


def bulk_decide_coordinator_bookings(
    db: Session,
    user: User,
    data: CoordinatorBulkDecisionRequest,
) -> CoordinatorBulkDecisionResponse:
    """Bulk approve or reject bookings in coordinator's assigned blocks."""
    success_count = 0
    failed_count = 0
    processed_ids: List[int] = []

    for b_id in data.booking_ids:
        try:
            decide_coordinator_booking(
                db=db,
                booking_id=b_id,
                user=user,
                decision_in=CoordinatorDecisionRequest(action=data.action, note=data.note),
            )
            success_count += 1
            processed_ids.append(b_id)
        except Exception:
            failed_count += 1

    return CoordinatorBulkDecisionResponse(
        message=f"Processed {len(data.booking_ids)} bookings: {success_count} succeeded, {failed_count} failed.",
        success_count=success_count,
        failed_count=failed_count,
        processed_ids=processed_ids,
    )


def preview_room_block_relocations(
    db: Session,
    user: User,
    data: CoordinatorRoomBlockPreviewRequest,
) -> RoomBlockPreviewResponse:
    """Preview affected bookings and suggested replacement rooms before confirming room block."""
    room = db.query(Room).options(joinedload(Room.block)).filter(Room.id == data.room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {data.room_id} not found",
        )

    my_block_ids = get_coordinator_block_ids(db, user)
    if room.block_id not in my_block_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You can only block rooms within your assigned blocks.",
        )

    if data.date_from > data.date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_from cannot be after date_to",
        )

    active_statuses = [
        BookingStatus.PENDING,
        BookingStatus.COORDINATOR_APPROVED,
        BookingStatus.APPROVED,
    ]

    query = (
        db.query(Booking)
        .options(
            joinedload(Booking.slot),
            joinedload(Booking.room).joinedload(Room.block),
        )
        .filter(
            Booking.room_id == room.id,
            Booking.date >= data.date_from,
            Booking.date <= data.date_to,
            Booking.status.in_(active_statuses),
        )
    )
    if data.slot_ids:
        query = query.filter(Booking.slot_id.in_(data.slot_ids))

    affected_bookings = query.order_by(Booking.date.asc(), Booking.slot_id.asc()).all()

    candidate_rooms = (
        db.query(Room)
        .options(joinedload(Room.block), joinedload(Room.facilities))
        .filter(Room.status == RoomStatus.ACTIVE, Room.id != room.id)
        .all()
    )

    reserved_slots: set = set()
    items: List[AffectedBookingItem] = []
    can_relocate_count = 0
    cannot_relocate_count = 0

    for b in affected_bookings:
        slot_label = b.slot.label if b.slot else f"Slot {b.slot_id}"
        rep_result = _find_best_candidate_room(
            db=db,
            booking=b,
            affected_room=room,
            candidate_rooms=candidate_rooms,
            reserved_slots=reserved_slots,
        )

        if rep_result:
            cand_room, _ = rep_result
            reserved_slots.add((cand_room.id, b.date, b.slot_id))
            can_relocate_count += 1
            items.append(
                AffectedBookingItem(
                    booking_id=b.id,
                    reference=b.reference,
                    requester_name=b.name,
                    requester_email=b.email,
                    date=b.date,
                    slot_id=b.slot_id,
                    slot_label=slot_label,
                    purpose=b.purpose,
                    expected_strength=b.expected_strength,
                    current_room_id=room.id,
                    current_room_name=room.name,
                    suggested_room_id=cand_room.id,
                    suggested_room_name=cand_room.name,
                    suggested_block_name=cand_room.block.name if cand_room.block else f"Block {cand_room.block_id}",
                    suggested_capacity=cand_room.capacity,
                    can_relocate=True,
                )
            )
        else:
            cannot_relocate_count += 1
            items.append(
                AffectedBookingItem(
                    booking_id=b.id,
                    reference=b.reference,
                    requester_name=b.name,
                    requester_email=b.email,
                    date=b.date,
                    slot_id=b.slot_id,
                    slot_label=slot_label,
                    purpose=b.purpose,
                    expected_strength=b.expected_strength,
                    current_room_id=room.id,
                    current_room_name=room.name,
                    suggested_room_id=None,
                    suggested_room_name=None,
                    suggested_block_name=None,
                    suggested_capacity=None,
                    can_relocate=False,
                )
            )

    return RoomBlockPreviewResponse(
        room_id=room.id,
        room_name=room.name,
        total_affected=len(affected_bookings),
        can_relocate_count=can_relocate_count,
        cannot_relocate_count=cannot_relocate_count,
        affected_bookings=items,
    )


def confirm_room_block_and_relocate(
    db: Session,
    user: User,
    data: ConfirmRelocationRequest,
) -> ConfirmRelocationResponse:
    """Block a room and automatically relocate affected bookings with notifications."""
    room = db.query(Room).options(joinedload(Room.block)).filter(Room.id == data.room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {data.room_id} not found",
        )

    my_block_ids = get_coordinator_block_ids(db, user)
    if room.block_id not in my_block_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You can only block rooms within your assigned blocks.",
        )

    if data.date_from > data.date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_from cannot be after date_to",
        )

    # 1. Update room type if mark_as_exam_hall
    if data.mark_as_exam_hall:
        room.room_type = RoomType.EXAM_HALL
        db.add(room)

    # 2. Create RoomBlocks
    slot_ids = data.slot_ids if data.slot_ids else [None]
    curr = data.date_from
    blocks_created = 0

    while curr <= data.date_to:
        for s_id in slot_ids:
            existing = (
                db.query(RoomBlock)
                .filter(
                    RoomBlock.room_id == room.id,
                    RoomBlock.date == curr,
                    RoomBlock.slot_id == s_id,
                    RoomBlock.is_released.is_(False),
                )
                .first()
            )
            if not existing:
                rb = RoomBlock(
                    room_id=room.id,
                    date=curr,
                    slot_id=s_id,
                    reason=data.reason,
                    note=data.note,
                    created_by=user.id,
                )
                db.add(rb)
                blocks_created += 1
        curr += timedelta(days=1)

    db.flush()

    # 3. Query affected bookings
    active_statuses = [
        BookingStatus.PENDING,
        BookingStatus.COORDINATOR_APPROVED,
        BookingStatus.APPROVED,
    ]
    query = (
        db.query(Booking)
        .options(
            joinedload(Booking.slot),
            joinedload(Booking.room).joinedload(Room.block),
        )
        .filter(
            Booking.room_id == room.id,
            Booking.date >= data.date_from,
            Booking.date <= data.date_to,
            Booking.status.in_(active_statuses),
        )
    )
    if data.slot_ids:
        query = query.filter(Booking.slot_id.in_(data.slot_ids))

    affected_bookings = query.order_by(Booking.date.asc(), Booking.slot_id.asc()).all()

    candidate_rooms = (
        db.query(Room)
        .options(joinedload(Room.block), joinedload(Room.facilities))
        .filter(Room.status == RoomStatus.ACTIVE, Room.id != room.id)
        .all()
    )

    reserved_slots: set = set()
    relocated_count = 0
    unresolved_count = 0

    for b in affected_bookings:
        rep_result = _find_best_candidate_room(
            db=db,
            booking=b,
            affected_room=room,
            candidate_rooms=candidate_rooms,
            reserved_slots=reserved_slots,
        )

        slot_label = b.slot.label if b.slot else f"Slot {b.slot_id}"

        if rep_result:
            cand_room, _ = rep_result
            reserved_slots.add((cand_room.id, b.date, b.slot_id))
            b.room_id = cand_room.id
            b.status = BookingStatus.RELOCATED
            b.decision_note = f"Relocated to {cand_room.name} ({cand_room.block.name if cand_room.block else ''}) due to {data.reason.value}"
            relocated_count += 1

            if b.email:
                try:
                    send_booking_relocated_email(
                        to_email=b.email,
                        recipient_name=b.name,
                        reference=b.reference,
                        original_room_name=room.name,
                        replacement_room_name=cand_room.name,
                        replacement_block_name=cand_room.block.name if cand_room.block else "",
                        booking_date=b.date,
                        slot_label=slot_label,
                        reason=data.reason.value,
                    )
                except Exception:
                    pass
        else:
            b.status = BookingStatus.RELOCATED
            b.decision_note = f"Room blocked for {data.reason.value}. Manual relocation required."
            unresolved_count += 1

            if b.email:
                try:
                    send_booking_relocated_email(
                        to_email=b.email,
                        recipient_name=b.name,
                        reference=b.reference,
                        original_room_name=room.name,
                        replacement_room_name=None,
                        replacement_block_name=None,
                        booking_date=b.date,
                        slot_label=slot_label,
                        reason=data.reason.value,
                    )
                except Exception:
                    pass

    db.commit()
    clear_timetable_cache()

    log_audit(
        db,
        action="ROOM_BLOCK_AND_RELOCATION",
        entity="RoomBlock",
        entity_id=room.id,
        actor_id=user.id,
        meta={
            "room_id": room.id,
            "room_name": room.name,
            "reason": data.reason.value,
            "date_from": str(data.date_from),
            "date_to": str(data.date_to),
            "blocks_created": blocks_created,
            "relocated_count": relocated_count,
            "unresolved_count": unresolved_count,
        },
    )

    return ConfirmRelocationResponse(
        message=f"Room blocked ({blocks_created} slots). {relocated_count} bookings relocated, {unresolved_count} unresolved.",
        blocks_created=blocks_created,
        relocated_count=relocated_count,
        unresolved_count=unresolved_count,
    )


def _find_best_candidate_room(
    db: Session,
    booking: Booking,
    affected_room: Room,
    candidate_rooms: List[Room],
    reserved_slots: set,
) -> Optional[Tuple[Room, float]]:
    """Helper to find optimal alternative room for an affected booking."""
    b_date = booking.date
    b_slot = booking.slot_id
    b_req_facilities = set(f.lower().strip() for f in (booking.required_facilities or []) if f.strip())
    target_room_type = affected_room.room_type

    feasible_candidates: List[Tuple[float, Room]] = []
    active_statuses = [
        BookingStatus.PENDING,
        BookingStatus.COORDINATOR_APPROVED,
        BookingStatus.APPROVED,
    ]

    for cand in candidate_rooms:
        if cand.id == affected_room.id:
            continue
        if cand.status != RoomStatus.ACTIVE:
            continue
        if cand.capacity < booking.expected_strength:
            continue
        if cand.room_type != target_room_type:
            continue

        cand_facs = {f.name.lower().strip() for f in cand.facilities}
        if not b_req_facilities.issubset(cand_facs):
            continue

        if (cand.id, b_date, b_slot) in reserved_slots:
            continue

        # Check RoomBlock
        block_clash = (
            db.query(RoomBlock)
            .filter(
                RoomBlock.room_id == cand.id,
                RoomBlock.date == b_date,
                RoomBlock.is_released.is_(False),
                or_(RoomBlock.slot_id.is_(None), RoomBlock.slot_id == b_slot),
            )
            .first()
        )
        if block_clash:
            continue

        # Check TimetableEntry
        weekday = b_date.weekday()
        tt_clash = (
            db.query(TimetableEntry)
            .filter(
                TimetableEntry.room_id == cand.id,
                TimetableEntry.day_of_week == weekday,
                TimetableEntry.slot_id == b_slot,
            )
            .first()
        )
        if tt_clash:
            continue

        # Check Booking
        b_clash = (
            db.query(Booking)
            .filter(
                Booking.room_id == cand.id,
                Booking.date == b_date,
                Booking.slot_id == b_slot,
                Booking.id != booking.id,
                Booking.status.in_(active_statuses),
            )
            .first()
        )
        if b_clash:
            continue

        block_delta = 0.0 if cand.block_id == affected_room.block_id else 60.0
        cap_delta = abs(cand.capacity - affected_room.capacity)
        floor_delta = abs(cand.floor - affected_room.floor) * 5.0
        wastage = (cand.capacity - booking.expected_strength) * 0.4
        change_score = block_delta + cap_delta + floor_delta + wastage
        feasible_candidates.append((change_score, cand))

    if feasible_candidates:
        feasible_candidates.sort(key=lambda x: x[0])
        return feasible_candidates[0][1], feasible_candidates[0][0]
    return None


def _format_room_block_item(rb: RoomBlock) -> BlockedRoomItem:
    today = date.today()
    if rb.is_released:
        computed_status = "RELEASED"
    elif rb.date == today:
        computed_status = "ACTIVE"
    elif rb.date > today:
        computed_status = "UPCOMING"
    else:
        computed_status = "PAST"

    creator_name = (
        rb.creator.name
        if rb.creator
        else (f"User #{rb.created_by}" if rb.created_by else "System")
    )
    releaser_name = (
        rb.releaser.name
        if rb.releaser
        else (f"User #{rb.released_by}" if rb.released_by else None)
    )

    room_obj = rb.room
    block_name = room_obj.block.name if room_obj and room_obj.block else f"Block {room_obj.block_id if room_obj else ''}"
    room_summary = BlockedRoomSummary(
        id=room_obj.id if room_obj else rb.room_id,
        name=room_obj.name if room_obj else f"Room {rb.room_id}",
        block=block_name,
        block_id=room_obj.block_id if room_obj else 0,
        floor=room_obj.floor if room_obj else 0,
        room_type=room_obj.room_type.value if room_obj else "CLASSROOM",
        type=room_obj.room_type.value if room_obj else "CLASSROOM",
        capacity=room_obj.capacity if room_obj else 0,
    )

    slot_label = rb.slot.label if rb.slot else "Full Day"
    reason_str = rb.reason.value if hasattr(rb.reason, "value") else str(rb.reason)

    return BlockedRoomItem(
        id=rb.id,
        is_indefinite=False,
        room_id=rb.room_id,
        room=room_summary,
        date=rb.date,
        slot_id=rb.slot_id,
        slot_label=slot_label,
        reason=reason_str,
        note=rb.note,
        created_by=creator_name,
        created_at=rb.created_at,
        released_at=rb.released_at,
        released_by=releaser_name,
        is_released=rb.is_released,
        status=computed_status,
    )


def list_coordinator_room_blocks(
    db: Session,
    user: User,
    status_filter: Optional[str] = "all",
    block_id: Optional[int] = None,
    room_id: Optional[int] = None,
    reason: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> BlockedRoomsResponse:
    """List paginated RoomBlock records for assigned blocks with filters and indefinite maintenance."""
    my_block_ids = get_coordinator_block_ids(db, user)

    if block_id:
        if block_id not in my_block_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: Requested block is not assigned to you.",
            )
        target_block_ids = [block_id]
    else:
        target_block_ids = my_block_ids

    if room_id:
        r_check = db.query(Room).filter(Room.id == room_id).first()
        if not r_check:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found.")
        if r_check.block_id not in my_block_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: Room is not in your assigned blocks.",
            )

    today = date.today()

    # Base query for RoomBlock
    rb_query = (
        db.query(RoomBlock)
        .join(Room, RoomBlock.room_id == Room.id)
        .options(
            joinedload(RoomBlock.room).joinedload(Room.block),
            joinedload(RoomBlock.slot),
            joinedload(RoomBlock.creator),
            joinedload(RoomBlock.releaser),
        )
    )

    if target_block_ids is not None:
        rb_query = rb_query.filter(Room.block_id.in_(target_block_ids))
    if room_id:
        rb_query = rb_query.filter(RoomBlock.room_id == room_id)
    if reason:
        rb_query = rb_query.filter(RoomBlock.reason == reason)
    if date_from:
        rb_query = rb_query.filter(RoomBlock.date >= date_from)
    if date_to:
        rb_query = rb_query.filter(RoomBlock.date <= date_to)
    if search and search.strip():
        term = f"%{search.strip()}%"
        rb_query = rb_query.filter(or_(Room.name.ilike(term), RoomBlock.note.ilike(term)))

    # Status filter
    norm_status = (status_filter or "all").lower().strip()
    if norm_status == "active":
        rb_query = rb_query.filter(RoomBlock.date == today, RoomBlock.is_released.is_(False))
    elif norm_status == "upcoming":
        rb_query = rb_query.filter(RoomBlock.date > today, RoomBlock.is_released.is_(False))
    elif norm_status == "past":
        rb_query = rb_query.filter(or_(RoomBlock.date < today, RoomBlock.is_released.is_(True)))

    rb_records = rb_query.order_by(RoomBlock.date.desc(), RoomBlock.id.desc()).all()
    formatted_rb_items = [_format_room_block_item(rb) for rb in rb_records]

    # Indefinite maintenance rooms
    indefinite_items: List[BlockedRoomItem] = []
    if norm_status in ("all", "active") and (not reason or reason.upper() == "MAINTENANCE") and not date_from and not date_to:
        maint_query = db.query(Room).options(joinedload(Room.block)).filter(Room.status == RoomStatus.MAINTENANCE)
        if target_block_ids is not None:
            maint_query = maint_query.filter(Room.block_id.in_(target_block_ids))
        if room_id:
            maint_query = maint_query.filter(Room.id == room_id)
        if search and search.strip():
            maint_query = maint_query.filter(Room.name.ilike(f"%{search.strip()}%"))

        maint_rooms = maint_query.all()
        for r in maint_rooms:
            # Check if this room already has an active block today in formatted items
            has_today_block = any(item.room_id == r.id and item.date == today and not item.is_released for item in formatted_rb_items)
            if not has_today_block:
                block_name = r.block.name if r.block else f"Block {r.block_id}"
                summary = BlockedRoomSummary(
                    id=r.id,
                    name=r.name,
                    block=block_name,
                    block_id=r.block_id,
                    floor=r.floor,
                    room_type=r.room_type.value,
                    type=r.room_type.value,
                    capacity=r.capacity,
                )
                indefinite_items.append(
                    BlockedRoomItem(
                        id=-r.id,
                        is_indefinite=True,
                        room_id=r.id,
                        room=summary,
                        date=today,
                        slot_id=None,
                        slot_label="Indefinite / Permanent",
                        reason="MAINTENANCE",
                        note=r.maintenance_note or "Indefinite maintenance (catalog status)",
                        created_by="Room Status",
                        created_at=None,
                        released_at=None,
                        released_by=None,
                        is_released=False,
                        status="ACTIVE",
                    )
                )

    all_items = indefinite_items + formatted_rb_items

    # Compute summary strip counts across assigned blocks
    count_scope = (
        db.query(RoomBlock)
        .join(Room, RoomBlock.room_id == Room.id)
    )
    if target_block_ids is not None:
        count_scope = count_scope.filter(Room.block_id.in_(target_block_ids))

    active_blocks_count = count_scope.filter(RoomBlock.date == today, RoomBlock.is_released.is_(False)).count()
    upcoming_blocks_count = count_scope.filter(RoomBlock.date > today, RoomBlock.is_released.is_(False)).count()

    maint_count_scope = db.query(Room).filter(Room.status == RoomStatus.MAINTENANCE)
    if target_block_ids is not None:
        maint_count_scope = maint_count_scope.filter(Room.block_id.in_(target_block_ids))
    maint_rooms_status_count = maint_count_scope.count()

    # Active maintenance blocks today count
    maint_blocks_today_count = count_scope.filter(
        RoomBlock.date == today,
        RoomBlock.is_released.is_(False),
        RoomBlock.reason == RoomBlockReason.MAINTENANCE,
    ).count()

    currently_blocked = active_blocks_count + maint_rooms_status_count
    upcoming_blocks = upcoming_blocks_count
    maintenance_rooms = maint_rooms_status_count + maint_blocks_today_count

    total = len(all_items)
    pages = math.ceil(total / page_size) if page_size > 0 else 0
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paged_items = all_items[start_idx:end_idx]

    return BlockedRoomsResponse(
        items=paged_items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        summary=BlockedRoomsSummaryCounts(
            currently_blocked=currently_blocked,
            upcoming_blocks=upcoming_blocks,
            maintenance_rooms=maintenance_rooms,
        ),
    )


def release_coordinator_room_block(
    db: Session,
    user: User,
    block_id: int,
) -> BlockedRoomItem:
    """Soft release a single RoomBlock, update audit log, clear cache, and notify waitlist."""
    rb = (
        db.query(RoomBlock)
        .options(
            joinedload(RoomBlock.room).joinedload(Room.block),
            joinedload(RoomBlock.slot),
            joinedload(RoomBlock.creator),
            joinedload(RoomBlock.releaser),
        )
        .filter(RoomBlock.id == block_id)
        .first()
    )
    if not rb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room block with id {block_id} not found.",
        )

    my_block_ids = get_coordinator_block_ids(db, user)
    if rb.room.block_id not in my_block_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You can only release blocks for rooms in your assigned blocks.",
        )

    today = date.today()
    if rb.date < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot release a block that has already completely passed.",
        )

    rb.is_released = True
    rb.released_at = datetime.now(timezone.utc)
    rb.released_by = user.id
    db.add(rb)

    # Revert room maintenance if no other active maintenance blocks exist
    if rb.room.status == RoomStatus.MAINTENANCE:
        other_maint = (
            db.query(RoomBlock)
            .filter(
                RoomBlock.room_id == rb.room_id,
                RoomBlock.date == today,
                RoomBlock.is_released.is_(False),
                RoomBlock.reason == RoomBlockReason.MAINTENANCE,
                RoomBlock.id != rb.id,
            )
            .first()
        )
        if not other_maint and not rb.room.maintenance_note:
            rb.room.status = RoomStatus.ACTIVE
            db.add(rb.room)

    log_audit(
        db,
        action="ROOM_BLOCK_RELEASED",
        entity="RoomBlock",
        entity_id=rb.id,
        actor_id=user.id,
        meta={
            "room_id": rb.room_id,
            "room_name": rb.room.name,
            "date": str(rb.date),
            "slot_id": rb.slot_id,
            "reason": rb.reason.value,
        },
    )

    # Notify waitlisted users
    try:
        wl_query = db.query(WaitlistEntry).filter(
            WaitlistEntry.room_id == rb.room_id,
            WaitlistEntry.date == rb.date,
            WaitlistEntry.notified.is_(False),
        )
        if rb.slot_id is not None:
            wl_query = wl_query.filter(WaitlistEntry.slot_id == rb.slot_id)
        for wl in wl_query.all():
            wl.notified = True
            wl.notified_at = datetime.now(timezone.utc)
            slot_lbl = rb.slot.label if rb.slot else "Full Day"
            threading.Thread(
                target=_send_waitlist_email,
                args=(wl.email, wl.name, rb.room.name, str(rb.date), slot_lbl),
                daemon=True,
            ).start()
    except Exception:
        pass

    db.commit()
    db.refresh(rb)
    clear_timetable_cache()

    return _format_room_block_item(rb)


def bulk_release_coordinator_room_blocks(
    db: Session,
    user: User,
    data: RoomBlockBulkReleaseRequest,
) -> RoomBlockBulkReleaseResponse:
    """Bulk soft release room blocks by a list of IDs or by room and date range."""
    my_block_ids = get_coordinator_block_ids(db, user)

    if data.ids:
        candidates = (
            db.query(RoomBlock)
            .options(joinedload(RoomBlock.room), joinedload(RoomBlock.slot))
            .filter(RoomBlock.id.in_(data.ids))
            .all()
        )
    elif data.room_id and data.date_from and data.date_to:
        if data.date_from > data.date_to:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date_from cannot be after date_to.",
            )
        q = (
            db.query(RoomBlock)
            .options(joinedload(RoomBlock.room), joinedload(RoomBlock.slot))
            .filter(
                RoomBlock.room_id == data.room_id,
                RoomBlock.date >= data.date_from,
                RoomBlock.date <= data.date_to,
                RoomBlock.is_released.is_(False),
            )
        )
        if data.reason:
            q = q.filter(RoomBlock.reason == data.reason)
        candidates = q.all()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either a list of block IDs or room_id with date_from and date_to.",
        )

    if not candidates:
        return RoomBlockBulkReleaseResponse(
            message="No matching room block records found.",
            released_count=0,
            released_ids=[],
        )

    # Permission check across all candidates
    for rb in candidates:
        if rb.room.block_id not in my_block_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: Room {rb.room.name} is not in your assigned blocks.",
            )

    today = date.today()
    eligible = [rb for rb in candidates if rb.date >= today and not rb.is_released]
    if not eligible:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No eligible blocks to release. Past blocks or already released blocks cannot be released.",
        )

    now_utc = datetime.now(timezone.utc)
    released_ids: List[int] = []

    for rb in eligible:
        rb.is_released = True
        rb.released_at = now_utc
        rb.released_by = user.id
        db.add(rb)
        released_ids.append(rb.id)

        if rb.room.status == RoomStatus.MAINTENANCE and not rb.room.maintenance_note:
            rb.room.status = RoomStatus.ACTIVE
            db.add(rb.room)

        log_audit(
            db,
            action="ROOM_BLOCK_RELEASED",
            entity="RoomBlock",
            entity_id=rb.id,
            actor_id=user.id,
            meta={
                "room_id": rb.room_id,
                "room_name": rb.room.name,
                "date": str(rb.date),
                "slot_id": rb.slot_id,
                "reason": rb.reason.value,
                "bulk": True,
            },
        )

        try:
            wl_query = db.query(WaitlistEntry).filter(
                WaitlistEntry.room_id == rb.room_id,
                WaitlistEntry.date == rb.date,
                WaitlistEntry.notified.is_(False),
            )
            if rb.slot_id is not None:
                wl_query = wl_query.filter(WaitlistEntry.slot_id == rb.slot_id)
            for wl in wl_query.all():
                wl.notified = True
                wl.notified_at = now_utc
                slot_lbl = rb.slot.label if rb.slot else "Full Day"
                threading.Thread(
                    target=_send_waitlist_email,
                    args=(wl.email, wl.name, rb.room.name, str(rb.date), slot_lbl),
                    daemon=True,
                ).start()
        except Exception:
            pass

    db.commit()
    clear_timetable_cache()

    return RoomBlockBulkReleaseResponse(
        message=f"Successfully released {len(released_ids)} room block record(s).",
        released_count=len(released_ids),
        released_ids=released_ids,
    )


def release_room_maintenance(
    db: Session,
    user: User,
    room_id: int,
) -> RoomMaintenanceReleaseResponse:
    """Set room status back to ACTIVE, clear maintenance_note, release today's maintenance blocks, and clear cache."""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with id {room_id} not found.",
        )

    my_block_ids = get_coordinator_block_ids(db, user)
    if room.block_id not in my_block_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Room is not in your assigned blocks.",
        )

    room.status = RoomStatus.ACTIVE
    room.maintenance_note = None
    db.add(room)

    # Release any active maintenance RoomBlocks for this room today or upcoming
    today = date.today()
    maint_blocks = (
        db.query(RoomBlock)
        .filter(
            RoomBlock.room_id == room.id,
            RoomBlock.date >= today,
            RoomBlock.is_released.is_(False),
            RoomBlock.reason == RoomBlockReason.MAINTENANCE,
        )
        .all()
    )
    now_utc = datetime.now(timezone.utc)
    for mb in maint_blocks:
        mb.is_released = True
        mb.released_at = now_utc
        mb.released_by = user.id
        db.add(mb)

    log_audit(
        db,
        action="ROOM_MAINTENANCE_RELEASED",
        entity="Room",
        entity_id=room.id,
        actor_id=user.id,
        meta={"room_id": room.id, "room_name": room.name},
    )

    db.commit()
    clear_timetable_cache()

    return RoomMaintenanceReleaseResponse(
        message=f"Room {room.name} has been set to ACTIVE and maintenance released.",
        room_id=room.id,
        room_name=room.name,
        status=room.status,
    )


def export_coordinator_bookings_csv(
    db: Session,
    user: User,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    block_id: Optional[int] = None,
    room_id: Optional[int] = None,
    status: Optional[BookingStatus] = None,
    search: Optional[str] = None,
) -> str:
    """Generate CSV string for filtered bookings within coordinator's assigned blocks."""
    my_block_ids = get_coordinator_block_ids(db, user)
    if not my_block_ids:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Reference", "Date", "Time Slot", "Room", "Block", "Department", "Requester Type", "Requester Name", "Roll No", "Email", "Phone", "Expected Strength", "Status", "HOD Approval Required", "Purpose", "Created At"])
        return output.getvalue()

    query = (
        db.query(Booking)
        .join(Room, Booking.room_id == Room.id)
        .options(
            joinedload(Booking.room).joinedload(Room.block),
            joinedload(Booking.slot),
            joinedload(Booking.department),
        )
        .filter(Room.block_id.in_(my_block_ids))
    )

    if block_id:
        if block_id in my_block_ids:
            query = query.filter(Room.block_id == block_id)
        else:
            query = query.filter(Booking.id == -1)

    if room_id:
        query = query.filter(Booking.room_id == room_id)

    if status:
        query = query.filter(Booking.status == status)

    if date_from:
        query = query.filter(Booking.date >= date_from)

    if date_to:
        query = query.filter(Booking.date <= date_to)

    if search:
        search_term = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Booking.reference).ilike(search_term),
                func.lower(Booking.name).ilike(search_term),
                func.lower(Booking.email).ilike(search_term),
                func.lower(Booking.roll_no).ilike(search_term),
                func.lower(Booking.purpose).ilike(search_term),
            )
        )

    bookings = query.order_by(Booking.date.desc(), Booking.id.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Reference",
        "Date",
        "Time Slot",
        "Room",
        "Block",
        "Department",
        "Requester Type",
        "Requester Name",
        "Roll No",
        "Email",
        "Phone",
        "Expected Strength",
        "Status",
        "HOD Approval Required",
        "Purpose",
        "Created At",
    ])

    for b in bookings:
        writer.writerow([
            b.reference,
            b.date.isoformat(),
            b.slot.label if b.slot else str(b.slot_id),
            b.room.name if b.room else str(b.room_id),
            b.room.block.name if b.room and b.room.block else "",
            b.department.code if b.department else str(b.department_id),
            b.requester_type.value,
            b.name,
            b.roll_no or "",
            b.email,
            b.phone,
            b.expected_strength,
            b.status.value,
            "Yes" if b.requires_hod_approval else "No",
            b.purpose,
            b.created_at.isoformat() if b.created_at else "",
        ])

    return output.getvalue()



