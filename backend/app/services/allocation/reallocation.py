from datetime import date
import json
import logging
from typing import List, Optional, Set, Tuple, Union
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.enums import BookingStatus, RoomBlockReason, RoomStatus
from app.models.room import Room
from app.models.room_block import RoomBlock
from app.models.timetable import TimetableEntry
from app.models.booking import Booking
from app.schemas.allocation import ReallocationResponse, RelocatedBookingSummary
from app.services.email import send_booking_relocated_email

logger = logging.getLogger(__name__)


def handle_room_unavailability(
    db: Session,
    room_id: int,
    reason: Union[RoomBlockReason, str],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    slot_id: Optional[int] = None,
    send_notifications: bool = True,
    preview_only: bool = False,
) -> ReallocationResponse:
    """
    Handles automatic relocation when a room enters MAINTENANCE or is blocked for an EXAM:
    1. Finds affected future bookings on the room.
    2. Computes replacement rooms with minimal disruption (prefer same block, similar capacity, same floor).
    3. Updates old bookings to RELOCATED status (pending coordinator confirmation).
    4. Sends notification emails to the requesters with replacement room details.
    """
    if start_date is None:
        start_date = date.today()

    reason_str = reason.value if hasattr(reason, "value") else str(reason)

    affected_room = db.query(Room).filter(Room.id == room_id).first()
    if not affected_room:
        raise ValueError(f"Room with id {room_id} not found.")

    # 1. Query affected active bookings
    active_statuses = [
        BookingStatus.PENDING,
        BookingStatus.COORDINATOR_APPROVED,
        BookingStatus.APPROVED,
    ]
    query = (
        db.query(Booking)
        .filter(
            Booking.room_id == room_id,
            Booking.date >= start_date,
            Booking.status.in_(active_statuses),
        )
    )
    if end_date:
        query = query.filter(Booking.date <= end_date)
    if slot_id:
        query = query.filter(Booking.slot_id == slot_id)

    affected_bookings = query.order_by(Booking.date.asc(), Booking.slot_id.asc()).all()

    if not affected_bookings:
        return ReallocationResponse(
            affected_count=0,
            relocated_count=0,
            unresolved_count=0,
            relocated_bookings=[],
            message="No affected future bookings found for this room.",
        )

    # Pre-fetch candidate rooms
    candidate_rooms = (
        db.query(Room)
        .filter(Room.status == RoomStatus.ACTIVE, Room.id != room_id)
        .all()
    )

    summaries: List[RelocatedBookingSummary] = []
    relocated_count = 0
    unresolved_count = 0

    # Track dynamically suggested rooms in this session to prevent suggesting same room to multiple bookings
    session_assigned_slots: Set[Tuple[int, date, int]] = set()

    for booking in affected_bookings:
        b_date = booking.date
        b_slot = booking.slot_id
        b_req_facilities = set(f.lower().strip() for f in (booking.required_facilities or []) if f.strip())
        target_room_type = affected_room.room_type

        # Find available candidates
        feasible_candidates: List[Tuple[float, Room]] = []

        for cand in candidate_rooms:
            # 1. Capacity check
            if cand.capacity < booking.expected_strength:
                continue

            # 2. Room type check
            if cand.room_type != target_room_type:
                continue

            # 3. Facilities check
            cand_facs = {f.name.lower().strip() for f in cand.facilities}
            if not b_req_facilities.issubset(cand_facs):
                continue

            # 4. Check session conflicts
            if (cand.id, b_date, b_slot) in session_assigned_slots:
                continue

            # 5. Check RoomBlock
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

            # 6. Check TimetableEntry
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

            # 7. Check existing active bookings
            existing_booking_clash = (
                db.query(Booking)
                .filter(
                    Booking.room_id == cand.id,
                    Booking.date == b_date,
                    Booking.slot_id == b_slot,
                    Booking.status.in_(active_statuses),
                )
                .first()
            )
            if existing_booking_clash:
                continue

            # Compute minimal change score (lower is better)
            # Prefer same block
            block_delta = 0.0 if cand.block_id == affected_room.block_id else 60.0
            # Prefer similar capacity
            cap_delta = abs(cand.capacity - affected_room.capacity)
            # Prefer same floor
            floor_delta = abs(cand.floor - affected_room.floor) * 5.0
            # Space wastage
            wastage = (cand.capacity - booking.expected_strength) * 0.4

            change_score = block_delta + cap_delta + floor_delta + wastage
            feasible_candidates.append((change_score, cand))

        feasible_candidates.sort(key=lambda x: x[0])

        if feasible_candidates:
            best_room = feasible_candidates[0][1]
            session_assigned_slots.add((best_room.id, b_date, b_slot))

            note_payload = {
                "action": "RELOCATED",
                "reason": reason_str,
                "original_room_id": affected_room.id,
                "original_room_name": affected_room.name,
                "suggested_room_id": best_room.id,
                "suggested_room_name": best_room.name,
                "suggested_block_name": best_room.block.name if best_room.block else f"Block {best_room.block_id}",
                "note": "Pending coordinator confirmation",
            }
            if not preview_only:
                booking.status = BookingStatus.RELOCATED
                booking.decision_note = json.dumps(note_payload)

            relocated_count += 1

            slot_label = booking.slot.label if booking.slot else f"Slot {booking.slot_id}"
            email_sent = False
            if not preview_only and send_notifications and booking.email:
                try:
                    email_sent = send_booking_relocated_email(
                        to_email=booking.email,
                        recipient_name=booking.name,
                        reference=booking.reference,
                        original_room_name=affected_room.name,
                        replacement_room_name=best_room.name,
                        replacement_block_name=best_room.block.name if best_room.block else "",
                        booking_date=booking.date,
                        slot_label=slot_label,
                        reason=reason_str,
                    )
                except Exception as ex:
                    logger.warning(f"Failed to send relocation email to {booking.email}: {ex}")

            summaries.append(
                RelocatedBookingSummary(
                    booking_id=booking.id,
                    reference=booking.reference,
                    requester_name=booking.name,
                    requester_email=booking.email,
                    date=booking.date,
                    slot_id=booking.slot_id,
                    original_room_id=affected_room.id,
                    original_room_name=affected_room.name,
                    replacement_room_id=best_room.id,
                    replacement_room_name=best_room.name,
                    replacement_block_name=best_room.block.name if best_room.block else "",
                    status=BookingStatus.RELOCATED.value if not preview_only else "PREVIEW",
                    email_sent=email_sent,
                )
            )
        else:
            # No automated replacement found
            note_payload = {
                "action": "RELOCATED",
                "reason": reason_str,
                "original_room_id": affected_room.id,
                "original_room_name": affected_room.name,
                "suggested_room_id": None,
                "suggested_room_name": None,
                "note": "No automated replacement room found with required capacity/facilities. Pending coordinator manual assignment.",
            }
            if not preview_only:
                booking.status = BookingStatus.RELOCATED
                booking.decision_note = json.dumps(note_payload)

            unresolved_count += 1

            slot_label = booking.slot.label if booking.slot else f"Slot {booking.slot_id}"
            email_sent = False
            if not preview_only and send_notifications and booking.email:
                try:
                    email_sent = send_booking_relocated_email(
                        to_email=booking.email,
                        recipient_name=booking.name,
                        reference=booking.reference,
                        original_room_name=affected_room.name,
                        replacement_room_name=None,
                        replacement_block_name=None,
                        booking_date=booking.date,
                        slot_label=slot_label,
                        reason=reason_str,
                    )
                except Exception as ex:
                    logger.warning(f"Failed to send relocation email to {booking.email}: {ex}")

            summaries.append(
                RelocatedBookingSummary(
                    booking_id=booking.id,
                    reference=booking.reference,
                    requester_name=booking.name,
                    requester_email=booking.email,
                    date=booking.date,
                    slot_id=booking.slot_id,
                    original_room_id=affected_room.id,
                    original_room_name=affected_room.name,
                    replacement_room_id=None,
                    replacement_room_name=None,
                    replacement_block_name=None,
                    status=BookingStatus.RELOCATED.value if not preview_only else "PREVIEW",
                    email_sent=email_sent,
                )
            )

    if not preview_only:
        db.commit()

    return ReallocationResponse(
        affected_count=len(affected_bookings),
        relocated_count=relocated_count,
        unresolved_count=unresolved_count,
        relocated_bookings=summaries,
        message=f"Processed {len(affected_bookings)} bookings: {relocated_count} relocated to replacement rooms, {unresolved_count} flagged for manual review.",
    )

