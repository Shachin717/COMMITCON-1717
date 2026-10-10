import logging
from datetime import date, datetime, time, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.booking import Booking
from app.models.enums import BookingStatus
from app.models.room import Room
from app.models.time_slot import TimeSlot
from app.services.audit import log_audit
from app.services.email import send_booking_reminder_email

logger = logging.getLogger(__name__)


def expire_pending_past_bookings(db: Session = None) -> int:
    """Find all PENDING or COORDINATOR_APPROVED bookings whose scheduled date or slot time has passed,

    transition them to REJECTED with an explanatory note, and record an audit log.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        today = date.today()
        now_time = datetime.now().time()

        # 1. Past dates
        stale_past_date = (
            db.query(Booking)
            .filter(
                Booking.date < today,
                Booking.status.in_([BookingStatus.PENDING, BookingStatus.COORDINATOR_APPROVED]),
            )
            .all()
        )

        # 2. Today's bookings where slot has already started or passed
        stale_today = (
            db.query(Booking)
            .join(TimeSlot, Booking.slot_id == TimeSlot.id)
            .filter(
                Booking.date == today,
                Booking.status.in_([BookingStatus.PENDING, BookingStatus.COORDINATOR_APPROVED]),
                TimeSlot.start_time <= now_time,
            )
            .all()
        )

        stale_bookings = list({b.id: b for b in (stale_past_date + stale_today)}.values())

        expired_count = 0
        for b in stale_bookings:
            prev_status = b.status.value
            b.status = BookingStatus.REJECTED
            b.decision_note = "Auto-expired: Booking date/time has passed without final approval."
            expired_count += 1

            log_audit(
                db,
                action="BOOKING_AUTO_EXPIRED",
                entity="Booking",
                entity_id=b.id,
                actor_id=None,
                meta={
                    "reference": b.reference,
                    "date": str(b.date),
                    "previous_status": prev_status,
                    "new_status": BookingStatus.REJECTED.value,
                    "reason": "Booking date/time passed",
                },
            )

        if expired_count > 0:
            db.commit()
            logger.info(f"Auto-expired {expired_count} stale pending bookings.")

        return expired_count
    except Exception as exc:
        db.rollback()
        logger.error(f"Error during auto-expiring past bookings: {exc}", exc_info=True)
        return 0
    finally:
        if should_close:
            db.close()


def auto_release_no_shows(db: Session = None, force_run: bool = False) -> int:
    """Auto-release approved bookings that have passed the grace period after slot start

    without check-in, freeing the room and notifying waitlists.
    """
    if not settings.AUTO_RELEASE_NO_SHOW and not force_run:
        return 0

    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        today = date.today()
        now_dt = datetime.now()
        grace_minutes = getattr(settings, "NO_SHOW_GRACE_MINUTES", 20)

        # Approved bookings for today that haven't checked in
        active_candidates = (
            db.query(Booking)
            .options(joinedload(Booking.slot), joinedload(Booking.room))
            .filter(
                Booking.date == today,
                Booking.status == BookingStatus.APPROVED,
                Booking.checked_in == False,
            )
            .all()
        )

        released_count = 0
        for b in active_candidates:
            if not b.slot:
                continue

            # Calculate slot start timestamp
            slot_start_dt = datetime.combine(today, b.slot.start_time)
            slot_end_dt = datetime.combine(today, b.slot.end_time)
            grace_threshold = slot_start_dt + timedelta(minutes=grace_minutes)

            # If now is past start + grace period
            if now_dt >= grace_threshold:
                prev_status = b.status.value
                b.status = BookingStatus.CANCELLED
                b.decision_note = (
                    f"Auto-released: Room marked as no-show after {grace_minutes} minute grace period."
                )
                released_count += 1

                log_audit(
                    db,
                    action="BOOKING_NO_SHOW_RELEASED",
                    entity="Booking",
                    entity_id=b.id,
                    actor_id=None,
                    meta={
                        "reference": b.reference,
                        "date": str(b.date),
                        "room_id": b.room_id,
                        "previous_status": prev_status,
                        "grace_minutes": grace_minutes,
                    },
                )

        if released_count > 0:
            db.commit()
            logger.info(f"Auto-released {released_count} no-show bookings.")

        return released_count
    except Exception as exc:
        db.rollback()
        logger.error(f"Error during no-show auto-release: {exc}", exc_info=True)
        return 0
    finally:
        if should_close:
            db.close()


def send_upcoming_booking_reminders(db: Session = None) -> int:
    """Send reminder email to students/faculty 1 hour before scheduled booking start."""
    if not getattr(settings, "REMINDER_JOB_ENABLED", True):
        return 0

    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        today = date.today()
        now_dt = datetime.now()

        # Target window: slot starts between 45 and 75 minutes from now
        window_start = (now_dt + timedelta(minutes=45)).time()
        window_end = (now_dt + timedelta(minutes=75)).time()

        upcoming_bookings = (
            db.query(Booking)
            .options(
                joinedload(Booking.slot),
                joinedload(Booking.room).joinedload(Room.block),
            )
            .join(TimeSlot, Booking.slot_id == TimeSlot.id)
            .filter(
                Booking.date == today,
                Booking.status == BookingStatus.APPROVED,
                Booking.reminder_sent == False,
                TimeSlot.start_time >= window_start,
                TimeSlot.start_time <= window_end,
            )
            .all()
        )

        sent_count = 0
        for b in upcoming_bookings:
            room_name = b.room.name if b.room else "Assigned Room"
            block_name = b.room.block.name if (b.room and b.room.block) else "Campus Block"
            slot_label = b.slot.label if b.slot else "Scheduled Slot"
            start_str = str(b.slot.start_time) if b.slot else ""
            end_str = str(b.slot.end_time) if b.slot else ""

            try:
                send_booking_reminder_email(
                    to_email=b.email,
                    reference=b.reference,
                    student_name=b.name,
                    room_name=room_name,
                    block_name=block_name,
                    date_str=str(b.date),
                    slot_label=slot_label,
                    start_time_str=start_str,
                    end_time_str=end_str,
                    purpose=b.purpose,
                )
            except Exception as mail_err:
                logger.warning(f"Could not dispatch reminder email for {b.reference}: {mail_err}")

            b.reminder_sent = True
            sent_count += 1
            log_audit(
                db,
                action="BOOKING_REMINDER_SENT",
                entity="Booking",
                entity_id=b.id,
                actor_id=None,
                meta={"reference": b.reference, "email": b.email, "date": str(b.date)},
            )

        if sent_count > 0:
            db.commit()
            logger.info(f"Dispatched {sent_count} booking reminder emails.")

        return sent_count
    except Exception as exc:
        db.rollback()
        logger.error(f"Error during upcoming booking reminder check: {exc}", exc_info=True)
        return 0
    finally:
        if should_close:
            db.close()
