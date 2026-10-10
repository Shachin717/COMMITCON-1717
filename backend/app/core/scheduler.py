import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.services.booking_expiry import (
    auto_release_no_shows,
    expire_pending_past_bookings,
    send_upcoming_booking_reminders,
)

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def start_scheduler():
    """Start APScheduler background jobs."""
    if not scheduler.running:
        # 1. Auto-expire old pending requests (every 15 min)
        scheduler.add_job(
            expire_pending_past_bookings,
            trigger=IntervalTrigger(minutes=15),
            id="expire_pending_past_bookings_job",
            name="Auto-expire pending bookings past their scheduled slot",
            replace_existing=True,
        )

        # 2. Reminder emails 1 hour before scheduled booking (every 10 min)
        scheduler.add_job(
            send_upcoming_booking_reminders,
            trigger=IntervalTrigger(minutes=10),
            id="send_upcoming_booking_reminders_job",
            name="Send reminder emails 1 hour before scheduled booking start",
            replace_existing=True,
        )

        # 3. Optional no-show auto-release after grace period (every 10 min)
        scheduler.add_job(
            auto_release_no_shows,
            trigger=IntervalTrigger(minutes=10),
            id="auto_release_no_shows_job",
            name="Auto-release unconfirmed no-show room bookings after grace period",
            replace_existing=True,
        )

        try:
            scheduler.start()
            logger.info("APScheduler background scheduler started.")
        except Exception as exc:
            logger.warning(f"Failed to start APScheduler: {exc}")


def shutdown_scheduler():
    """Shutdown APScheduler background scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler background scheduler stopped.")

