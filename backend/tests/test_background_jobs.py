from datetime import date, datetime, time, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.department import Department
from app.models.enums import BookingStatus, RequesterType, RoomType, UserRole
from app.models.room import Room
from app.models.time_slot import TimeSlot
from app.models.block import Block
from app.services.booking_expiry import (
    auto_release_no_shows,
    expire_pending_past_bookings,
    send_upcoming_booking_reminders,
)


@pytest.fixture
def sample_setup(db_session: Session):
    dept = Department(name="Computer Science", code="CSE", hod_approval_required=True)
    block = Block(name="Academic Block A", description="Main campus block")
    db_session.add_all([dept, block])
    db_session.flush()

    room = Room(
        name="A-101",
        block_id=block.id,
        floor=1,
        room_type=RoomType.CLASSROOM,
        capacity=60,
        department_id=dept.id,
    )
    # A slot for current window testing
    slot_past = TimeSlot(
        label="Past Slot",
        start_time=(datetime.now() - timedelta(minutes=60)).time(),
        end_time=(datetime.now() - timedelta(minutes=10)).time(),
        order=1,
    )
    slot_upcoming = TimeSlot(
        label="Upcoming Slot",
        start_time=(datetime.now() + timedelta(minutes=50)).time(),
        end_time=(datetime.now() + timedelta(minutes=110)).time(),
        order=2,
    )
    db_session.add_all([room, slot_past, slot_upcoming])
    db_session.commit()

    return {
        "dept": dept,
        "block": block,
        "room": room,
        "slot_past": slot_past,
        "slot_upcoming": slot_upcoming,
    }


def test_expire_pending_past_bookings(db_session: Session, sample_setup):
    yesterday = date.today() - timedelta(days=1)
    booking_past = Booking(
        reference="BK-EXP-01",
        room_id=sample_setup["room"].id,
        date=yesterday,
        slot_id=sample_setup["slot_past"].id,
        purpose="Stale Event",
        expected_strength=30,
        required_facilities=[],
        status=BookingStatus.PENDING,
        requester_type=RequesterType.STUDENT,
        roll_no="CS001",
        name="Stale Student",
        department_id=sample_setup["dept"].id,
        phone="9876543210",
        email="stale@college.edu",
    )
    db_session.add(booking_past)
    db_session.commit()

    expired = expire_pending_past_bookings(db=db_session)
    assert expired >= 1

    db_session.refresh(booking_past)
    assert booking_past.status == BookingStatus.REJECTED
    assert "Auto-expired" in booking_past.decision_note


def test_auto_release_no_shows(db_session: Session, sample_setup):
    today = date.today()
    booking_noshow = Booking(
        reference="BK-NOSHOW-01",
        room_id=sample_setup["room"].id,
        date=today,
        slot_id=sample_setup["slot_past"].id,
        purpose="No show lecture",
        expected_strength=30,
        required_facilities=[],
        status=BookingStatus.APPROVED,
        requester_type=RequesterType.STUDENT,
        roll_no="CS002",
        name="No Show Student",
        department_id=sample_setup["dept"].id,
        phone="9876543210",
        email="noshow@college.edu",
        checked_in=False,
    )
    db_session.add(booking_noshow)
    db_session.commit()

    released = auto_release_no_shows(db=db_session, force_run=True)
    assert released >= 1

    db_session.refresh(booking_noshow)
    assert booking_noshow.status == BookingStatus.CANCELLED
    assert "no-show" in booking_noshow.decision_note


def test_send_upcoming_booking_reminders(db_session: Session, sample_setup):
    today = date.today()
    booking_upcoming = Booking(
        reference="BK-REMIND-01",
        room_id=sample_setup["room"].id,
        date=today,
        slot_id=sample_setup["slot_upcoming"].id,
        purpose="Imminent Seminar",
        expected_strength=40,
        required_facilities=[],
        status=BookingStatus.APPROVED,
        requester_type=RequesterType.STUDENT,
        roll_no="CS003",
        name="Upcoming Student",
        department_id=sample_setup["dept"].id,
        phone="9876543210",
        email="remind@college.edu",
        reminder_sent=False,
    )
    db_session.add(booking_upcoming)
    db_session.commit()

    sent = send_upcoming_booking_reminders(db=db_session)
    assert sent >= 1

    db_session.refresh(booking_upcoming)
    assert booking_upcoming.reminder_sent is True


def test_public_check_in_endpoint(client: TestClient, db_session: Session, sample_setup):
    today = date.today()
    booking = Booking(
        reference="BK-CHECKIN-01",
        room_id=sample_setup["room"].id,
        date=today,
        slot_id=sample_setup["slot_upcoming"].id,
        purpose="Lab Test",
        expected_strength=25,
        required_facilities=[],
        status=BookingStatus.APPROVED,
        requester_type=RequesterType.STUDENT,
        roll_no="CS004",
        name="Active Student",
        department_id=sample_setup["dept"].id,
        phone="9876543210",
        email="checkin@college.edu",
        checked_in=False,
    )
    db_session.add(booking)
    db_session.commit()

    resp = client.post(f"/api/public/bookings/{booking.reference}/check-in")
    assert resp.status_code == 200
    assert resp.json()["checked_in"] is True

    db_session.refresh(booking)
    assert booking.checked_in is True
