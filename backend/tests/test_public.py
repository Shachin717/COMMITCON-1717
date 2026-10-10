import concurrent.futures
from datetime import date, datetime, time, timedelta, timezone
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter
from app.core.security import hash_token
from app.main import app as fastapi_app
from app.models.audit_log import AuditLog
from app.models.block import Block
from app.models.booking import Booking
from app.models.department import Department
from app.models.enums import BookingStatus, RequesterType, RoomBlockReason, RoomStatus, RoomType
from app.models.facility import Facility, RoomFacility
from app.models.room import Room
from app.models.room_block import RoomBlock
from app.models.time_slot import TimeSlot
from app.models.timetable import TimetableEntry
from app.models.waitlist import WaitlistEntry


@pytest.fixture
def setup_public_data(db_session: Session):
    """Seed test data for public endpoints testing."""
    # Departments
    dept_cs = Department(name="Computer Science & Engineering", code="CSE", hod_approval_required=True)
    dept_me = Department(name="Mechanical Engineering", code="MECH", hod_approval_required=False)
    db_session.add_all([dept_cs, dept_me])
    db_session.flush()

    # Blocks
    block_a = Block(name="Main Academic Block A", description="Engineering lecture halls")
    block_b = Block(name="Science Block B", description="Laboratories & Auditoriums")
    db_session.add_all([block_a, block_b])
    db_session.flush()

    # Facilities
    fac_proj = Facility(name="projector")
    fac_ac = Facility(name="ac")
    fac_board = Facility(name="smart_board")
    fac_pcs = Facility(name="pcs")
    db_session.add_all([fac_proj, fac_ac, fac_board, fac_pcs])
    db_session.flush()

    # Time slots
    slot1 = TimeSlot(label="09:00 - 10:00", start_time=time(9, 0), end_time=time(10, 0), order=1)
    slot2 = TimeSlot(label="10:00 - 11:00", start_time=time(10, 0), end_time=time(11, 0), order=2)
    slot3 = TimeSlot(label="11:00 - 12:00", start_time=time(11, 0), end_time=time(12, 0), order=3)
    slot4 = TimeSlot(label="12:00 - 13:00", start_time=time(12, 0), end_time=time(13, 0), order=4)
    db_session.add_all([slot1, slot2, slot3, slot4])
    db_session.flush()

    # Rooms
    # Room 1: Classroom in Block A, cap 50, has projector & ac
    room1 = Room(
        name="A-101",
        block_id=block_a.id,
        floor=1,
        room_type=RoomType.CLASSROOM,
        capacity=50,
        status=RoomStatus.ACTIVE,
    )
    # Room 2: Classroom in Block A, cap 120, has projector, ac, smart_board
    room2 = Room(
        name="A-201",
        block_id=block_a.id,
        floor=2,
        room_type=RoomType.CLASSROOM,
        capacity=120,
        status=RoomStatus.ACTIVE,
    )
    # Room 3: CS Lab in Block B, cap 40, department CS (HOD approval required), has pcs, ac
    room3 = Room(
        name="CS-LAB-01",
        block_id=block_b.id,
        floor=1,
        room_type=RoomType.LAB,
        capacity=40,
        department_id=dept_cs.id,
        status=RoomStatus.ACTIVE,
    )
    # Room 4: Mechanical Lab in Block B, cap 40, department ME (No HOD approval), has pcs
    room4 = Room(
        name="ME-LAB-01",
        block_id=block_b.id,
        floor=1,
        room_type=RoomType.LAB,
        capacity=40,
        department_id=dept_me.id,
        status=RoomStatus.ACTIVE,
    )
    # Room 5: Seminar Hall in Block A, under MAINTENANCE
    room5 = Room(
        name="A-AUDITORIUM",
        block_id=block_a.id,
        floor=3,
        room_type=RoomType.SEMINAR_HALL,
        capacity=200,
        status=RoomStatus.MAINTENANCE,
        maintenance_note="Audio system renovation",
    )
    db_session.add_all([room1, room2, room3, room4, room5])
    db_session.flush()

    # Link Facilities
    db_session.add_all([
        RoomFacility(room_id=room1.id, facility_id=fac_proj.id),
        RoomFacility(room_id=room1.id, facility_id=fac_ac.id),
        RoomFacility(room_id=room2.id, facility_id=fac_proj.id),
        RoomFacility(room_id=room2.id, facility_id=fac_ac.id),
        RoomFacility(room_id=room2.id, facility_id=fac_board.id),
        RoomFacility(room_id=room3.id, facility_id=fac_pcs.id),
        RoomFacility(room_id=room3.id, facility_id=fac_ac.id),
        RoomFacility(room_id=room4.id, facility_id=fac_pcs.id),
    ])
    db_session.commit()

    return {
        "dept_cs": dept_cs,
        "dept_me": dept_me,
        "block_a": block_a,
        "block_b": block_b,
        "slot1": slot1,
        "slot2": slot2,
        "slot3": slot3,
        "slot4": slot4,
        "room1": room1,
        "room2": room2,
        "room3": room3,
        "room4": room4,
        "room5": room5,
    }


def test_public_availability_basic_and_fit_score(client: TestClient, setup_public_data, db_session: Session):
    """Test availability search with fit score ranking (best-fit capacity first)."""
    room1 = setup_public_data["room1"]  # cap 50
    room2 = setup_public_data["room2"]  # cap 120
    slot1 = setup_public_data["slot1"]
    test_date = str(date.today() + timedelta(days=2))

    # Request min_capacity = 45. Room1 (cap 50) should have a higher fit score than Room2 (cap 120)
    res = client.get(
        f"/api/public/availability?date={test_date}&slot_ids={slot1.id}&min_capacity=45&room_type=CLASSROOM"
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_available"] == 2
    rooms = data["available_rooms"]
    assert rooms[0]["id"] == room1.id
    assert rooms[1]["id"] == room2.id
    assert rooms[0]["fit_score"] > rooms[1]["fit_score"]
    assert rooms[0]["block_name"] == "Main Academic Block A"
    assert "projector" in rooms[0]["facilities"]


def test_public_availability_exclusions(client: TestClient, setup_public_data, db_session: Session):
    """Test that RoomBlock, TimetableEntry, maintenance status, and active bookings exclude rooms."""
    room1 = setup_public_data["room1"]
    room2 = setup_public_data["room2"]
    room3 = setup_public_data["room3"]
    room5 = setup_public_data["room5"]  # MAINTENANCE
    slot1 = setup_public_data["slot1"]
    slot2 = setup_public_data["slot2"]
    target_date = date.today() + timedelta(days=3)
    target_date_str = str(target_date)

    # 1. Room5 is in MAINTENANCE -> should never appear in availability
    res = client.get(f"/api/public/availability?date={target_date_str}&slot_ids={slot1.id}")
    room_ids = [r["id"] for r in res.json()["available_rooms"]]
    assert room5.id not in room_ids

    # 2. Add RoomBlock on room1 for slot1
    rb = RoomBlock(
        room_id=room1.id,
        date=target_date,
        slot_id=slot1.id,
        reason=RoomBlockReason.MAINTENANCE,
        note="Air conditioner filter clean",
    )
    db_session.add(rb)

    # 3. Add TimetableEntry for room2 on target_date weekday for slot1
    weekday = target_date.weekday()
    te = TimetableEntry(
        room_id=room2.id,
        day_of_week=weekday,
        slot_id=slot1.id,
        department_id=setup_public_data["dept_cs"].id,
        subject="Algorithms",
        faculty_name="Dr. Alan",
    )
    db_session.add(te)

    # 4. Add active Booking for room3 on target_date for slot1
    bk = Booking(
        reference="BK-TEST-1234",
        room_id=room3.id,
        date=target_date,
        slot_id=slot1.id,
        purpose="Lab Test",
        expected_strength=30,
        status=BookingStatus.PENDING,
        requester_type=RequesterType.STUDENT,
        roll_no="21CS001",
        name="Student One",
        department_id=setup_public_data["dept_cs"].id,
        class_name="CS-3A",
        phone="9876543210",
        email="student1@college.edu",
    )
    db_session.add(bk)
    db_session.commit()

    # Query availability for slot1
    res = client.get(f"/api/public/availability?date={target_date_str}&slot_ids={slot1.id}")
    avail_ids = [r["id"] for r in res.json()["available_rooms"]]
    assert room1.id not in avail_ids  # Blocked by RoomBlock
    assert room2.id not in avail_ids  # Blocked by TimetableEntry
    assert room3.id not in avail_ids  # Blocked by active Booking

    # But room1 and room2 should be available for slot2
    res_slot2 = client.get(f"/api/public/availability?date={target_date_str}&slot_ids={slot2.id}")
    slot2_avail_ids = [r["id"] for r in res_slot2.json()["available_rooms"]]
    assert room1.id in slot2_avail_ids
    assert room2.id in slot2_avail_ids


def test_public_availability_suggestions_when_none_available(client: TestClient, setup_public_data, db_session: Session):
    """Test that suggestions (nearest free slots and other rooms) are returned when nothing is available."""
    target_date = str(date.today() + timedelta(days=5))
    slot1 = setup_public_data["slot1"]

    # Request impossible capacity (e.g. 999)
    res = client.get(f"/api/public/availability?date={target_date}&slot_ids={slot1.id}&min_capacity=999")
    assert res.status_code == 200
    data = res.json()
    assert data["total_available"] == 0
    assert data["suggestions"] is not None
    assert "nearest_free_slots" in data["suggestions"]
    assert "other_rooms" in data["suggestions"]
    assert len(data["suggestions"]["other_rooms"]) > 0


def test_public_timetable_grid(client: TestClient, setup_public_data, db_session: Session):
    """Test GET /api/public/timetable returns matrix and grid with FREE / BOOKED / CLASS / MAINTENANCE / EXAM."""
    room1 = setup_public_data["room1"]
    room2 = setup_public_data["room2"]
    room3 = setup_public_data["room3"]
    room4 = setup_public_data["room4"]
    room5 = setup_public_data["room5"]  # Room in MAINTENANCE
    slot1 = setup_public_data["slot1"]
    slot2 = setup_public_data["slot2"]
    slot3 = setup_public_data["slot3"]

    target_date = date.today() + timedelta(days=4)
    weekday = target_date.weekday()

    # 1. EXAM block on room1 slot1
    rb_exam = RoomBlock(
        room_id=room1.id,
        date=target_date,
        slot_id=slot1.id,
        reason=RoomBlockReason.EXAM,
        note="End Semester Exam",
    )
    # 2. CLASS on room2 slot2
    te_class = TimetableEntry(
        room_id=room2.id,
        day_of_week=weekday,
        slot_id=slot2.id,
        department_id=setup_public_data["dept_cs"].id,
        subject="Operating Systems",
        faculty_name="Prof. Linus",
    )
    # 3. BOOKED on room3 slot3
    bk_booked = Booking(
        reference="BK-TIMETABLE-1",
        room_id=room3.id,
        date=target_date,
        slot_id=slot3.id,
        purpose="Robotics Workshop",
        expected_strength=25,
        status=BookingStatus.APPROVED,
        requester_type=RequesterType.STUDENT,
        roll_no="21CS099",
        name="Alex Smith",
        department_id=setup_public_data["dept_cs"].id,
        class_name="CS-4A",
        phone="9876543210",
        email="alex@college.edu",
    )
    db_session.add_all([rb_exam, te_class, bk_booked])
    db_session.commit()

    res = client.get(f"/api/public/timetable?date={target_date}")
    assert res.status_code == 200
    data = res.json()
    grid = data["grid"]

    # Verify cell statuses:
    assert grid[str(room1.id)][str(slot1.id)] == "EXAM"
    assert grid[str(room2.id)][str(slot2.id)] == "CLASS"
    assert grid[str(room3.id)][str(slot3.id)] == "BOOKED"
    assert grid[str(room5.id)][str(slot1.id)] == "MAINTENANCE"
    assert grid[str(room4.id)][str(slot1.id)] == "FREE"

    # Test filtering by block_id
    block_a_id = setup_public_data["block_a"].id
    res_block = client.get(f"/api/public/timetable?date={target_date}&block_id={block_a_id}")
    assert res_block.status_code == 200
    block_rooms = res_block.json()["rooms"]
    for r in block_rooms:
        assert r["block_id"] == block_a_id


def test_public_booking_flow_and_acknowledgement(client: TestClient, setup_public_data, db_session: Session):
    """Test successful booking submission, pending status, reference code, cancel token, and HOD logic."""
    room3 = setup_public_data["room3"]  # LAB with dept_cs (hod_approval_required=True)
    slot1 = setup_public_data["slot1"]
    dept_cs = setup_public_data["dept_cs"]
    target_date = str(date.today() + timedelta(days=2))

    payload = {
        "room_id": room3.id,
        "date": target_date,
        "slot_id": slot1.id,
        "purpose": "Machine Learning Research Lab Session",
        "expected_strength": 30,
        "required_facilities": ["pcs"],
        "roll_no": "22CS101",
        "name": "David Miller",
        "department_id": dept_cs.id,
        "class_name": "CSE-3B",
        "phone": "+91 98765 43210",
        "email": "david.miller@student.college.edu",
    }

    res = client.post("/api/public/bookings", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "PENDING"
    assert data["reference"].startswith("BK-")
    assert len(data["cancel_token"]) > 20
    assert data["requires_hod_approval"] is True  # LAB in dept with hod_approval_required=True

    # Verify cancel token is stored ONLY as hash in the database
    db_booking = db_session.query(Booking).filter(Booking.reference == data["reference"]).first()
    assert db_booking is not None
    assert db_booking.cancel_token_hash is not None
    assert db_booking.cancel_token_hash != data["cancel_token"]
    assert db_booking.cancel_token_hash == hash_token(data["cancel_token"])

    # Lookup status using GET /api/public/bookings/{reference}?email=
    lookup_res = client.get(f"/api/public/bookings/{data['reference']}?email=david.miller@student.college.edu")
    assert lookup_res.status_code == 200
    status_data = lookup_res.json()
    assert status_data["reference"] == data["reference"]
    assert status_data["status"] == "PENDING"
    assert status_data["room_name"] == room3.name

    # Mismatched email should return 404
    wrong_email_res = client.get(f"/api/public/bookings/{data['reference']}?email=wrong@student.college.edu")
    assert wrong_email_res.status_code == 404


def test_public_booking_validation_errors(client: TestClient, setup_public_data):
    """Test validation of Roll No, Name, Phone, and past date."""
    room1 = setup_public_data["room1"]
    slot1 = setup_public_data["slot1"]
    dept_cs = setup_public_data["dept_cs"]

    base_payload = {
        "room_id": room1.id,
        "date": str(date.today() + timedelta(days=2)),
        "slot_id": slot1.id,
        "purpose": "Study Group",
        "expected_strength": 20,
        "required_facilities": [],
        "roll_no": "21CS001",
        "name": "Alice",
        "department_id": dept_cs.id,
        "class_name": "CS-1A",
        "phone": "9876543210",
        "email": "alice@college.edu",
    }

    # 1. Past date
    bad_date = base_payload.copy()
    bad_date["date"] = "2020-01-01"
    res = client.post("/api/public/bookings", json=bad_date)
    assert res.status_code == 400

    # 2. Invalid phone
    bad_phone = base_payload.copy()
    bad_phone["phone"] = "abc"
    res = client.post("/api/public/bookings", json=bad_phone)
    assert res.status_code == 422

    # 3. Expected strength exceeds capacity
    exceed_cap = base_payload.copy()
    exceed_cap["expected_strength"] = 500
    res = client.post("/api/public/bookings", json=exceed_cap)
    assert res.status_code == 400


def test_public_booking_conflict_graceful_handling(client: TestClient, setup_public_data, db_session: Session):
    """Test that booking an occupied slot returns 409 Conflict with friendly message and suggested alternatives."""
    room1 = setup_public_data["room1"]
    slot1 = setup_public_data["slot1"]
    dept_cs = setup_public_data["dept_cs"]
    target_date = str(date.today() + timedelta(days=2))

    payload = {
        "room_id": room1.id,
        "date": target_date,
        "slot_id": slot1.id,
        "purpose": "Initial Event",
        "expected_strength": 20,
        "required_facilities": [],
        "roll_no": "21CS001",
        "name": "First Requester",
        "department_id": dept_cs.id,
        "class_name": "CS-1A",
        "phone": "9876543210",
        "email": "first@college.edu",
    }
    # First booking succeeds
    res1 = client.post("/api/public/bookings", json=payload)
    assert res1.status_code == 201

    # Second booking for same room, date, slot
    payload2 = payload.copy()
    payload2["roll_no"] = "21CS002"
    payload2["name"] = "Second Requester"
    payload2["email"] = "second@college.edu"

    res2 = client.post("/api/public/bookings", json=payload2)
    assert res2.status_code == 409
    data = res2.json()
    assert "message" in data
    assert "suggestions" in data
    assert "nearest_free_slots" in data["suggestions"]


def test_public_cancellation_by_token(client: TestClient, setup_public_data, db_session: Session):
    """Test cancelling booking by secure cancel token, frees slot, writes AuditLog."""
    room1 = setup_public_data["room1"]
    slot1 = setup_public_data["slot1"]
    dept_cs = setup_public_data["dept_cs"]
    target_date = str(date.today() + timedelta(days=2))

    # Create booking
    booking_res = client.post(
        "/api/public/bookings",
        json={
            "room_id": room1.id,
            "date": target_date,
            "slot_id": slot1.id,
            "purpose": "Workshop",
            "expected_strength": 25,
            "roll_no": "21CS010",
            "name": "Charlie",
            "department_id": dept_cs.id,
            "class_name": "CS-2A",
            "phone": "9876543210",
            "email": "charlie@college.edu",
        },
    )
    assert booking_res.status_code == 201
    cancel_token = booking_res.json()["cancel_token"]
    reference = booking_res.json()["reference"]

    # Cancel via token
    cancel_res = client.post(
        "/api/public/bookings/cancel",
        json={"cancel_token": cancel_token},
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"

    # Verify status in DB
    db_bk = db_session.query(Booking).filter(Booking.reference == reference).first()
    assert db_bk.status == BookingStatus.CANCELLED

    # Verify slot is freed: booking again should now SUCCEED!
    new_res = client.post(
        "/api/public/bookings",
        json={
            "room_id": room1.id,
            "date": target_date,
            "slot_id": slot1.id,
            "purpose": "New Workshop",
            "expected_strength": 25,
            "roll_no": "21CS020",
            "name": "Dan",
            "department_id": dept_cs.id,
            "class_name": "CS-2A",
            "phone": "9876543210",
            "email": "dan@college.edu",
        },
    )
    assert new_res.status_code == 201

    # Verify AuditLog written
    audit = db_session.query(AuditLog).filter(
        AuditLog.action == "BOOKING_CANCELLED",
        AuditLog.entity_id == str(db_bk.id),
    ).first()
    assert audit is not None
    assert audit.meta["reference"] == reference


def test_public_cancellation_by_otp(client: TestClient, setup_public_data, db_session: Session):
    """Test cancelling booking by reference + email OTP."""
    room1 = setup_public_data["room1"]
    slot2 = setup_public_data["slot2"]
    dept_cs = setup_public_data["dept_cs"]
    target_date = str(date.today() + timedelta(days=2))

    # Create booking
    booking_res = client.post(
        "/api/public/bookings",
        json={
            "room_id": room1.id,
            "date": target_date,
            "slot_id": slot2.id,
            "purpose": "Project Review",
            "expected_strength": 20,
            "roll_no": "21CS030",
            "name": "Elena",
            "department_id": dept_cs.id,
            "class_name": "CS-3A",
            "phone": "9876543210",
            "email": "elena@college.edu",
        },
    )
    assert booking_res.status_code == 201
    reference = booking_res.json()["reference"]

    # 1. Request OTP
    otp_req = client.post(
        "/api/public/bookings/cancel/request-otp",
        json={"reference": reference, "email": "elena@college.edu"},
    )
    assert otp_req.status_code == 200

    # Retrieve OTP code from DB in test
    from app.models.otp import OtpCode
    otp_record = (
        db_session.query(OtpCode)
        .filter(OtpCode.email == "elena@college.edu", OtpCode.purpose == "booking_cancel")
        .order_by(OtpCode.id.desc())
        .first()
    )
    assert otp_record is not None

    # Cancel using invalid OTP
    bad_cancel = client.post(
        "/api/public/bookings/cancel",
        json={"reference": reference, "email": "elena@college.edu", "otp": "000000"},
    )
    assert bad_cancel.status_code == 400

    # For valid OTP, verify using simulated OTP or updating code_hash
    test_otp = "123456"
    otp_record.code_hash = hash_token(test_otp)
    db_session.commit()

    good_cancel = client.post(
        "/api/public/bookings/cancel",
        json={"reference": reference, "email": "elena@college.edu", "otp": test_otp},
    )
    assert good_cancel.status_code == 200
    assert good_cancel.json()["status"] == "CANCELLED"


def test_waitlist_joined_and_notified_on_cancellation(client: TestClient, setup_public_data, db_session: Session):
    """Test joining a waitlist and automatically notifying the waitlisted user when a booking is cancelled."""
    room1 = setup_public_data["room1"]
    slot3 = setup_public_data["slot3"]
    dept_cs = setup_public_data["dept_cs"]
    target_date = str(date.today() + timedelta(days=2))

    # 1. Create booking
    b_res = client.post(
        "/api/public/bookings",
        json={
            "room_id": room1.id,
            "date": target_date,
            "slot_id": slot3.id,
            "purpose": "Annual Seminar",
            "expected_strength": 40,
            "roll_no": "21CS040",
            "name": "Grace",
            "department_id": dept_cs.id,
            "class_name": "CS-4A",
            "phone": "9876543210",
            "email": "grace@college.edu",
        },
    )
    assert b_res.status_code == 201
    cancel_token = b_res.json()["cancel_token"]

    # 2. Join waitlist for the same room, date, slot
    w_res = client.post(
        "/api/public/waitlist",
        json={
            "room_id": room1.id,
            "date": target_date,
            "slot_id": slot3.id,
            "name": "Waitlisted Student",
            "email": "waitlisted@college.edu",
            "phone": "9876543210",
            "roll_no": "21CS045",
            "department_id": dept_cs.id,
            "class_name": "CS-4A",
        },
    )
    assert w_res.status_code == 201
    waitlist_id = w_res.json()["id"]

    # Verify waitlist record
    w_entry = db_session.query(WaitlistEntry).filter(WaitlistEntry.id == waitlist_id).first()
    assert w_entry.notified is False

    # 3. Cancel the booking
    cancel_res = client.post(
        "/api/public/bookings/cancel",
        json={"cancel_token": cancel_token},
    )
    assert cancel_res.status_code == 200

    # 4. Verify waitlisted student is marked as notified and AuditLog is created
    db_session.refresh(w_entry)
    assert w_entry.notified is True
    assert w_entry.notified_at is not None

    audit = db_session.query(AuditLog).filter(
        AuditLog.action == "WAITLIST_NOTIFIED",
        AuditLog.entity_id == str(waitlist_id),
    ).first()
    assert audit is not None
    assert audit.meta["email"] == "waitlisted@college.edu"


def test_concurrency_simultaneous_booking_same_slot(client: TestClient, setup_public_data, db_session: Session):
    """
    Concurrency Test: Two requests attempt to book the exact same room and slot simultaneously.
    Exactly one must succeed (201 Created), while the other must receive 409 Conflict.
    The database must strictly maintain zero overlapping active bookings.
    """
    from app.core.database import get_db
    from tests.conftest import TestingSessionLocal

    room1 = setup_public_data["room1"]
    slot4 = setup_public_data["slot4"]
    dept_cs = setup_public_data["dept_cs"]
    target_date = str(date.today() + timedelta(days=2))

    payload_a = {
        "room_id": room1.id,
        "date": target_date,
        "slot_id": slot4.id,
        "purpose": "Concurrent Request A",
        "expected_strength": 20,
        "roll_no": "21CS050",
        "name": "User Alpha",
        "department_id": dept_cs.id,
        "class_name": "CS-1A",
        "phone": "9876543210",
        "email": "user.alpha@college.edu",
    }

    payload_b = {
        "room_id": room1.id,
        "date": target_date,
        "slot_id": slot4.id,
        "purpose": "Concurrent Request B",
        "expected_strength": 25,
        "roll_no": "21CS051",
        "name": "User Beta",
        "department_id": dept_cs.id,
        "class_name": "CS-1B",
        "phone": "9876543210",
        "email": "user.beta@college.edu",
    }

    conn = db_session.bind

    def override_concurrent_db():
        session = TestingSessionLocal(bind=conn)
        try:
            yield session
        finally:
            session.close()

    fastapi_app.dependency_overrides[get_db] = override_concurrent_db

    try:
        def book(payload):
            # Each concurrent request executes through TestClient
            with TestClient(fastapi_app) as thread_client:
                return thread_client.post("/api/public/bookings", json=payload)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f_a = executor.submit(book, payload_a)
            f_b = executor.submit(book, payload_b)
            res_a = f_a.result()
            res_b = f_b.result()

        statuses = sorted([res_a.status_code, res_b.status_code])
        # Exactly one 201 Created and one 409 Conflict
        assert statuses == [201, 409], f"Unexpected responses: {res_a.status_code}, {res_b.status_code}"

        # Verify 409 response contains friendly message and suggested alternatives
        conflict_res = res_a if res_a.status_code == 409 else res_b
        conflict_data = conflict_res.json()
        assert "message" in conflict_data
        assert "suggestions" in conflict_data

        # Verify exactly ONE active booking in DB for that room, date, and slot
        verify_sess = TestingSessionLocal(bind=conn)
        try:
            active_count = (
                verify_sess.query(Booking)
                .filter(
                    Booking.room_id == room1.id,
                    Booking.date == target_date,
                    Booking.slot_id == slot4.id,
                    Booking.status.in_([BookingStatus.PENDING, BookingStatus.COORDINATOR_APPROVED, BookingStatus.APPROVED]),
                )
                .count()
            )
            assert active_count == 1
        finally:
            verify_sess.close()
    finally:
        def override_get_db():
            yield db_session
        fastapi_app.dependency_overrides[get_db] = override_get_db


def test_public_rate_limiting_enforcement(client: TestClient, setup_public_data):
    """Test that rate limiting blocks excessive public requests when enabled."""
    original_enabled = limiter.enabled
    try:
        limiter.enabled = True
        test_date = str(date.today() + timedelta(days=2))
        responses = []
        for _ in range(70):
            res = client.get(f"/api/public/availability?date={test_date}")
            responses.append(res.status_code)
            if res.status_code == 429:
                break

        assert 429 in responses, "Expected 429 Too Many Requests when exceeding rate limit"
    finally:
        limiter.enabled = original_enabled
