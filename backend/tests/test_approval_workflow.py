from datetime import date, datetime, time, timedelta
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.audit_log import AuditLog
from app.models.block import Block, BlockCoordinator
from app.models.booking import Booking
from app.models.department import Department
from app.models.enums import BookingStatus, RequesterType, RoomBlockReason, RoomStatus, RoomType, UserRole
from app.models.room import Room
from app.models.room_block import RoomBlock
from app.models.time_slot import TimeSlot
from app.models.user import User
from app.services.booking_expiry import expire_pending_past_bookings


@pytest.fixture
def approval_setup(db_session: Session):
    password_hash = hash_password("Secret123!")

    # Departments
    dept_cse = Department(name="Computer Science", code="CSE", hod_approval_required=True)
    dept_ece = Department(name="Electronics", code="ECE", hod_approval_required=False)
    db_session.add_all([dept_cse, dept_ece])
    db_session.flush()

    # Blocks
    block_a = Block(name="Block A", description="Engineering Block")
    block_b = Block(name="Block B", description="Science Block")
    db_session.add_all([block_a, block_b])
    db_session.flush()

    # Users
    coord_a = User(
        name="Coordinator A",
        email="coord_a@college.edu",
        password_hash=password_hash,
        role=UserRole.COORDINATOR,
        is_active=True,
    )
    coord_b = User(
        name="Coordinator B",
        email="coord_b@college.edu",
        password_hash=password_hash,
        role=UserRole.COORDINATOR,
        is_active=True,
    )
    hod_cse = User(
        name="HOD CSE",
        email="hod_cse@college.edu",
        password_hash=password_hash,
        role=UserRole.HOD,
        department_id=dept_cse.id,
        is_active=True,
    )
    hod_ece = User(
        name="HOD ECE",
        email="hod_ece@college.edu",
        password_hash=password_hash,
        role=UserRole.HOD,
        department_id=dept_ece.id,
        is_active=True,
    )
    db_session.add_all([coord_a, coord_b, hod_cse, hod_ece])
    db_session.flush()

    # Assign coordinator A -> Block A, coordinator B -> Block B
    assign_a = BlockCoordinator(user_id=coord_a.id, block_id=block_a.id)
    assign_b = BlockCoordinator(user_id=coord_b.id, block_id=block_b.id)
    db_session.add_all([assign_a, assign_b])
    db_session.flush()

    # Time slots
    slot1 = TimeSlot(label="09:00 - 10:00", start_time=time(9, 0), end_time=time(10, 0), order=1)
    slot2 = TimeSlot(label="10:00 - 11:00", start_time=time(10, 0), end_time=time(11, 0), order=2)
    db_session.add_all([slot1, slot2])
    db_session.flush()

    # Rooms
    # Room in Block A - Regular CLASSROOM
    room_a1 = Room(
        name="A-101",
        block_id=block_a.id,
        floor=1,
        room_type=RoomType.CLASSROOM,
        capacity=50,
        department_id=dept_cse.id,
        status=RoomStatus.ACTIVE,
    )
    # Room in Block A - LAB (requires HOD approval since CSE.hod_approval_required is True)
    room_a_lab = Room(
        name="A-LAB-01",
        block_id=block_a.id,
        floor=1,
        room_type=RoomType.LAB,
        capacity=40,
        department_id=dept_cse.id,
        status=RoomStatus.ACTIVE,
    )
    # Room in Block B - Regular CLASSROOM
    room_b1 = Room(
        name="B-101",
        block_id=block_b.id,
        floor=1,
        room_type=RoomType.CLASSROOM,
        capacity=60,
        department_id=dept_ece.id,
        status=RoomStatus.ACTIVE,
    )
    # Room in Block B - LAB (ECE.hod_approval_required is False)
    room_b_lab = Room(
        name="B-LAB-01",
        block_id=block_b.id,
        floor=1,
        room_type=RoomType.LAB,
        capacity=30,
        department_id=dept_ece.id,
        status=RoomStatus.ACTIVE,
    )
    db_session.add_all([room_a1, room_a_lab, room_b1, room_b_lab])
    db_session.commit()

    return {
        "dept_cse": dept_cse,
        "dept_ece": dept_ece,
        "block_a": block_a,
        "block_b": block_b,
        "coord_a": coord_a,
        "coord_b": coord_b,
        "hod_cse": hod_cse,
        "hod_ece": hod_ece,
        "slot1": slot1,
        "slot2": slot2,
        "room_a1": room_a1,
        "room_a_lab": room_a_lab,
        "room_b1": room_b1,
        "room_b_lab": room_b_lab,
    }


def auth_header(user: User) -> dict:
    token = create_access_token(
        subject=user.id,
        extra_claims={"role": user.role.value, "email": user.email},
    )
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# 1. State Machine Transitions & Permission Checks
# =========================================================================

def test_coordinator_cannot_approve_other_block(client: TestClient, approval_setup, db_session: Session):
    data = approval_setup
    target_date = date.today() + timedelta(days=2)

    # Booking in Block B
    booking_b = Booking(
        reference="BK-TEST-B1",
        room_id=data["room_b1"].id,
        date=target_date,
        slot_id=data["slot1"].id,
        purpose="Guest Lecture",
        expected_strength=30,
        status=BookingStatus.PENDING,
        requires_hod_approval=False,
        requester_type=RequesterType.STUDENT,
        name="John Doe",
        department_id=data["dept_ece"].id,
        phone="9876543210",
        email="john@college.edu",
    )
    db_session.add(booking_b)
    db_session.commit()

    # Coordinator A attempts to approve booking in Block B -> 403 Forbidden
    resp = client.post(
        f"/api/coordinator/bookings/{booking_b.id}/decision",
        json={"action": "approve", "note": "Trying cross-block approval"},
        headers=auth_header(data["coord_a"]),
    )
    assert resp.status_code == 403
    assert "outside your coordinator assignment" in resp.json()["detail"]


def test_coordinator_approves_regular_room_direct_approved(client: TestClient, approval_setup, db_session: Session):
    """PENDING -> (Coordinator Approves, requires_hod_approval=False) -> APPROVED.

    Dispatches confirmation email with ICS calendar attachment.
    """
    data = approval_setup
    target_date = date.today() + timedelta(days=2)

    booking = Booking(
        reference="BK-TEST-A1",
        room_id=data["room_a1"].id,
        date=target_date,
        slot_id=data["slot1"].id,
        purpose="Project Demo",
        expected_strength=40,
        status=BookingStatus.PENDING,
        requires_hod_approval=False,
        requester_type=RequesterType.STUDENT,
        name="Alice Smith",
        department_id=data["dept_cse"].id,
        phone="9876543210",
        email="alice@college.edu",
    )
    db_session.add(booking)
    db_session.commit()

    with patch("app.services.coordinator.send_booking_approved_email") as mock_email:
        mock_email.return_value = True

        resp = client.post(
            f"/api/coordinator/bookings/{booking.id}/decision",
            json={"action": "approve", "note": "Approved by Coordinator A"},
            headers=auth_header(data["coord_a"]),
        )
        assert resp.status_code == 200
        res_data = resp.json()
        assert res_data["status"] == BookingStatus.APPROVED.value
        assert res_data["decision_note"] == "Approved by Coordinator A"

        # Verify email dispatched with ICS details
        assert mock_email.called
        kwargs = mock_email.call_args[1]
        assert kwargs["to_email"] == "alice@college.edu"
        assert kwargs["reference"] == "BK-TEST-A1"

    # Verify audit log
    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_id == str(booking.id), AuditLog.action == "BOOKING_APPROVED")
        .first()
    )
    assert audit is not None
    assert audit.actor_id == data["coord_a"].id


def test_coordinator_approves_lab_requires_hod_approval(client: TestClient, approval_setup, db_session: Session):
    """PENDING -> (Coordinator Approves, requires_hod_approval=True) -> COORDINATOR_APPROVED.

    No approval confirmation email sent yet.
    """
    data = approval_setup
    target_date = date.today() + timedelta(days=2)

    booking = Booking(
        reference="BK-TEST-LAB1",
        room_id=data["room_a_lab"].id,
        date=target_date,
        slot_id=data["slot1"].id,
        purpose="Compiler Design Lab Session",
        expected_strength=35,
        status=BookingStatus.PENDING,
        requires_hod_approval=True,
        requester_type=RequesterType.STUDENT,
        name="Bob Johnson",
        department_id=data["dept_cse"].id,
        phone="9876543210",
        email="bob@college.edu",
    )
    db_session.add(booking)
    db_session.commit()

    with patch("app.services.coordinator.send_booking_approved_email") as mock_email:
        resp = client.post(
            f"/api/coordinator/bookings/{booking.id}/decision",
            json={"action": "approve", "note": "Coordinator recommends approval"},
            headers=auth_header(data["coord_a"]),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == BookingStatus.COORDINATOR_APPROVED.value
        # Email NOT sent yet because HOD approval is required
        assert not mock_email.called

    # Check audit log
    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_id == str(booking.id), AuditLog.action == "BOOKING_COORDINATOR_APPROVED")
        .first()
    )
    assert audit is not None


def test_coordinator_rejects_booking(client: TestClient, approval_setup, db_session: Session):
    """PENDING -> (Coordinator Rejects) -> REJECTED with note and rejection email."""
    data = approval_setup
    target_date = date.today() + timedelta(days=2)

    booking = Booking(
        reference="BK-TEST-REJ",
        room_id=data["room_a1"].id,
        date=target_date,
        slot_id=data["slot1"].id,
        purpose="Music Practice",
        expected_strength=20,
        status=BookingStatus.PENDING,
        requires_hod_approval=False,
        requester_type=RequesterType.STUDENT,
        name="Charlie",
        department_id=data["dept_cse"].id,
        phone="9876543210",
        email="charlie@college.edu",
    )
    db_session.add(booking)
    db_session.commit()

    with patch("app.services.coordinator.send_booking_rejected_email") as mock_email:
        mock_email.return_value = True

        resp = client.post(
            f"/api/coordinator/bookings/{booking.id}/decision",
            json={"action": "reject", "note": "Academic classrooms not for band practice"},
            headers=auth_header(data["coord_a"]),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == BookingStatus.REJECTED.value

        assert mock_email.called
        kwargs = mock_email.call_args[1]
        assert kwargs["to_email"] == "charlie@college.edu"
        assert kwargs["rejection_reason"] == "Academic classrooms not for band practice"


# =========================================================================
# 2. HOD Approvals & Permissions
# =========================================================================

def test_hod_pending_approvals_and_approval_transition(client: TestClient, approval_setup, db_session: Session):
    """COORDINATOR_APPROVED -> (HOD Approves) -> APPROVED with confirmation email + ICS."""
    data = approval_setup
    target_date = date.today() + timedelta(days=3)

    booking = Booking(
        reference="BK-TEST-HOD1",
        room_id=data["room_a_lab"].id,
        date=target_date,
        slot_id=data["slot1"].id,
        purpose="AI Research Workshop",
        expected_strength=30,
        status=BookingStatus.COORDINATOR_APPROVED,
        requires_hod_approval=True,
        requester_type=RequesterType.STUDENT,
        name="Dave Brown",
        department_id=data["dept_cse"].id,
        phone="9876543210",
        email="dave@college.edu",
    )
    db_session.add(booking)
    db_session.commit()

    # 1. HOD checks pending approvals
    resp = client.get(
        "/api/hod/approvals/pending",
        headers=auth_header(data["hod_cse"]),
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["hod_approval_required"] is True
    assert len(res_data["pending_bookings"]) >= 1
    assert any(b["reference"] == "BK-TEST-HOD1" for b in res_data["pending_bookings"])

    # 2. HOD approves booking
    with patch("app.services.hod.send_booking_approved_email") as mock_email:
        mock_email.return_value = True

        resp_dec = client.post(
            f"/api/hod/bookings/{booking.id}/decision",
            json={"action": "approve", "note": "HOD approval granted for AI workshop"},
            headers=auth_header(data["hod_cse"]),
        )
        assert resp_dec.status_code == 200
        assert resp_dec.json()["status"] == BookingStatus.APPROVED.value

        assert mock_email.called
        kwargs = mock_email.call_args[1]
        assert kwargs["to_email"] == "dave@college.edu"

    # Audit log check
    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_id == str(booking.id), AuditLog.action == "BOOKING_HOD_APPROVED")
        .first()
    )
    assert audit is not None
    assert audit.actor_id == data["hod_cse"].id


def test_hod_rejects_booking(client: TestClient, approval_setup, db_session: Session):
    """COORDINATOR_APPROVED -> (HOD Rejects) -> REJECTED with rejection email."""
    data = approval_setup
    target_date = date.today() + timedelta(days=3)

    booking = Booking(
        reference="BK-TEST-HODREJ",
        room_id=data["room_a_lab"].id,
        date=target_date,
        slot_id=data["slot1"].id,
        purpose="Unofficial Workshop",
        expected_strength=25,
        status=BookingStatus.COORDINATOR_APPROVED,
        requires_hod_approval=True,
        requester_type=RequesterType.STUDENT,
        name="Eve",
        department_id=data["dept_cse"].id,
        phone="9876543210",
        email="eve@college.edu",
    )
    db_session.add(booking)
    db_session.commit()

    with patch("app.services.hod.send_booking_rejected_email") as mock_email:
        mock_email.return_value = True

        resp = client.post(
            f"/api/hod/bookings/{booking.id}/decision",
            json={"action": "reject", "note": "Lab maintenance scheduled on this date"},
            headers=auth_header(data["hod_cse"]),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == BookingStatus.REJECTED.value

        assert mock_email.called
        kwargs = mock_email.call_args[1]
        assert kwargs["to_email"] == "eve@college.edu"
        assert kwargs["rejection_reason"] == "Lab maintenance scheduled on this date"


def test_hod_cannot_decide_other_department_booking(client: TestClient, approval_setup, db_session: Session):
    """HOD of ECE cannot decide a CSE booking."""
    data = approval_setup
    target_date = date.today() + timedelta(days=3)

    booking = Booking(
        reference="BK-TEST-HOD-CROSS",
        room_id=data["room_a_lab"].id,
        date=target_date,
        slot_id=data["slot1"].id,
        purpose="CSE Lab work",
        expected_strength=30,
        status=BookingStatus.COORDINATOR_APPROVED,
        requires_hod_approval=True,
        requester_type=RequesterType.STUDENT,
        name="Frank",
        department_id=data["dept_cse"].id,
        phone="9876543210",
        email="frank@college.edu",
    )
    db_session.add(booking)
    db_session.commit()

    # HOD of ECE tries to approve CSE lab booking -> 400 or 403
    resp = client.post(
        f"/api/hod/bookings/{booking.id}/decision",
        json={"action": "approve", "note": "Cross department attempt"},
        headers=auth_header(data["hod_ece"]),
    )
    # dept_ece has hod_approval_required=False so it raises 400, or 403 for department mismatch
    assert resp.status_code in (400, 403)


def test_hod_disabled_approval_returns_flag(client: TestClient, approval_setup, db_session: Session):
    """If department has hod_approval_required=False, pending returns empty list and flag false."""
    data = approval_setup
    resp = client.get(
        "/api/hod/approvals/pending",
        headers=auth_header(data["hod_ece"]),
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["hod_approval_required"] is False
    assert res_data["pending_bookings"] == []


# =========================================================================
# 3. Overview, Room Blocking, History & Timetable
# =========================================================================

def test_coordinator_get_all_blocks_overview(client: TestClient, approval_setup, db_session: Session):
    data = approval_setup
    target_date = date.today() + timedelta(days=4)

    # Put a booking in Room A-101
    booking = Booking(
        reference="BK-TEST-OV1",
        room_id=data["room_a1"].id,
        date=target_date,
        slot_id=data["slot1"].id,
        purpose="Overview test",
        expected_strength=30,
        status=BookingStatus.APPROVED,
        requires_hod_approval=False,
        requester_type=RequesterType.STUDENT,
        name="George",
        department_id=data["dept_cse"].id,
        phone="9876543210",
        email="george@college.edu",
    )
    db_session.add(booking)
    db_session.commit()

    # Query overview for coordinator A
    resp = client.get(
        f"/api/coordinator/overview?date={target_date}&slot_id={data['slot1'].id}",
        headers=auth_header(data["coord_a"]),
    )
    assert resp.status_code == 200
    overview = resp.json()
    assert overview["total_rooms"] == 4
    assert overview["booked_rooms_count"] >= 1

    # Check is_my_block flag
    rooms = {r["room_id"]: r for r in overview["rooms"]}
    assert rooms[data["room_a1"].id]["is_my_block"] is True
    assert rooms[data["room_b1"].id]["is_my_block"] is False  # Block B is read-only


def test_coordinator_block_room_for_maintenance_and_exam(client: TestClient, approval_setup, db_session: Session):
    data = approval_setup
    date_from = date.today() + timedelta(days=5)
    date_to = date.today() + timedelta(days=6)

    # 1. Block room A-101 for EXAM and mark as EXAM_HALL
    resp = client.post(
        "/api/coordinator/room-blocks",
        json={
            "room_id": data["room_a1"].id,
            "date_from": str(date_from),
            "date_to": str(date_to),
            "slot_ids": [data["slot1"].id, data["slot2"].id],
            "reason": "EXAM",
            "note": "Mid-term examinations",
            "mark_as_exam_hall": True,
        },
        headers=auth_header(data["coord_a"]),
    )
    assert resp.status_code == 201
    res_data = resp.json()
    assert res_data["created_count"] == 4  # 2 days x 2 slots

    # Verify room type updated to EXAM_HALL
    room = db_session.query(Room).filter(Room.id == data["room_a1"].id).first()
    assert room.room_type == RoomType.EXAM_HALL

    # Verify coordinator cannot block room in other block
    resp_cross = client.post(
        "/api/coordinator/room-blocks",
        json={
            "room_id": data["room_b1"].id,
            "date_from": str(date_from),
            "date_to": str(date_to),
            "reason": "MAINTENANCE",
            "note": "Painting",
        },
        headers=auth_header(data["coord_a"]),
    )
    assert resp_cross.status_code == 403


def test_coordinator_timetable_and_history(client: TestClient, approval_setup, db_session: Session):
    data = approval_setup
    target_date = date.today() + timedelta(days=1)

    # Coordinator timetable
    resp = client.get(
        f"/api/coordinator/timetable?date={target_date}&block_id={data['block_a'].id}",
        headers=auth_header(data["coord_a"]),
    )
    assert resp.status_code == 200
    tt = resp.json()
    assert "matrix" in tt
    assert "slots" in tt
    assert "grid" in tt

    # Coordinator History
    resp_hist = client.get(
        "/api/coordinator/history",
        headers=auth_header(data["coord_a"]),
    )
    assert resp_hist.status_code == 200
    assert "items" in resp_hist.json()


def test_hod_history(client: TestClient, approval_setup, db_session: Session):
    data = approval_setup
    resp = client.get(
        "/api/hod/bookings/history",
        headers=auth_header(data["hod_cse"]),
    )
    assert resp.status_code == 200
    assert "items" in resp.json()


# =========================================================================
# 4. Auto-expiration of Stale Bookings
# =========================================================================

def test_auto_expire_past_pending_bookings(approval_setup, db_session: Session):
    data = approval_setup
    past_date = date.today() - timedelta(days=2)

    past_booking_pending = Booking(
        reference="BK-PAST-1",
        room_id=data["room_a1"].id,
        date=past_date,
        slot_id=data["slot1"].id,
        purpose="Stale unapproved booking",
        expected_strength=20,
        status=BookingStatus.PENDING,
        requires_hod_approval=False,
        requester_type=RequesterType.STUDENT,
        name="Past Student",
        department_id=data["dept_cse"].id,
        phone="9876543210",
        email="past@college.edu",
    )
    future_booking_pending = Booking(
        reference="BK-FUT-1",
        room_id=data["room_a1"].id,
        date=date.today() + timedelta(days=2),
        slot_id=data["slot1"].id,
        purpose="Future booking",
        expected_strength=20,
        status=BookingStatus.PENDING,
        requires_hod_approval=False,
        requester_type=RequesterType.STUDENT,
        name="Future Student",
        department_id=data["dept_cse"].id,
        phone="9876543210",
        email="future@college.edu",
    )
    db_session.add_all([past_booking_pending, future_booking_pending])
    db_session.commit()

    # Run auto-expire job
    expired_count = expire_pending_past_bookings(db=db_session)
    assert expired_count >= 1

    db_session.refresh(past_booking_pending)
    db_session.refresh(future_booking_pending)

    assert past_booking_pending.status == BookingStatus.REJECTED
    assert "Auto-expired" in past_booking_pending.decision_note
    assert future_booking_pending.status == BookingStatus.PENDING

    # Check audit log for auto-expiry
    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_id == str(past_booking_pending.id), AuditLog.action == "BOOKING_AUTO_EXPIRED")
        .first()
    )
    assert audit is not None


def test_hod_summary_and_labs_endpoints(client: TestClient, approval_setup, db_session: Session):
    data = approval_setup
    hod = data["hod_cse"]
    headers = auth_header(hod)

    # 1. Summary
    resp_sum = client.get("/api/hod/summary", headers=headers)
    assert resp_sum.status_code == 200
    res_data = resp_sum.json()
    assert res_data["department_name"] == "Computer Science"
    assert res_data["department_code"] == "CSE"
    assert res_data["hod_approval_required"] is True
    assert "utilization_rate" in res_data
    assert len(res_data["bookings_per_day"]) == 7
    assert len(res_data["room_type_usage"]) >= 2

    # 2. Labs
    resp_labs = client.get("/api/hod/labs", headers=headers)
    assert resp_labs.status_code == 200
    labs_data = resp_labs.json()
    assert isinstance(labs_data, list)
    # A-LAB-01 belongs to CSE
    lab_names = [l["name"] for l in labs_data]
    assert "A-LAB-01" in lab_names

    # 3. Rooms
    resp_rooms = client.get("/api/hod/rooms", headers=headers)
    assert resp_rooms.status_code == 200
    rooms_data = resp_rooms.json()
    assert isinstance(rooms_data, list)
    room_names = [r["name"] for r in rooms_data]
    assert "A-LAB-01" in room_names

    # 4. CSV Export
    resp_csv = client.get("/api/hod/bookings/export", headers=headers)
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]
    assert "Reference,Date,Slot" in resp_csv.text

    # 5. History with filters
    resp_hist = client.get(
        f"/api/hod/bookings/history?room_id={data['room_a_lab'].id}&student=Student",
        headers=headers,
    )
    assert resp_hist.status_code == 200
    assert "items" in resp_hist.json()

