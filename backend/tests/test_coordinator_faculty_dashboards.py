from datetime import date, time, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.block import Block, BlockCoordinator
from app.models.booking import Booking
from app.models.department import Department
from app.models.enums import BookingStatus, RequesterType, RoomBlockReason, RoomStatus, RoomType, UserRole
from app.models.room import Room
from app.models.time_slot import TimeSlot
from app.models.user import User


@pytest.fixture
def dash_setup(db_session: Session):
    pwd = hash_password("Secret123!")

    dept = Department(name="Information Technology", code="IT", hod_approval_required=False)
    block1 = Block(name="Block C", description="North Wing")
    block2 = Block(name="Block D", description="South Wing")
    db_session.add_all([dept, block1, block2])
    db_session.flush()

    coord = User(
        name="Coord C",
        email="coord_c@college.edu",
        password_hash=pwd,
        role=UserRole.COORDINATOR,
        is_active=True,
    )
    faculty = User(
        name="Prof Turing",
        email="turing@college.edu",
        password_hash=pwd,
        role=UserRole.FACULTY,
        department_id=dept.id,
        is_active=True,
    )
    db_session.add_all([coord, faculty])
    db_session.flush()

    db_session.add(BlockCoordinator(block_id=block1.id, user_id=coord.id))

    slot1 = TimeSlot(label="Period 1", start_time=time(9, 0), end_time=time(10, 0), order=1)
    slot2 = TimeSlot(label="Period 2", start_time=time(10, 0), end_time=time(11, 0), order=2)
    db_session.add_all([slot1, slot2])
    db_session.flush()


    room1 = Room(
        name="C-101",
        block_id=block1.id,
        floor=1,
        capacity=50,
        room_type=RoomType.CLASSROOM,
        status=RoomStatus.ACTIVE,
        facilities=[],
    )
    room2 = Room(
        name="C-102",
        block_id=block1.id,
        floor=1,
        capacity=60,
        room_type=RoomType.CLASSROOM,
        status=RoomStatus.ACTIVE,
        facilities=[],
    )
    room_other = Room(
        name="D-101",
        block_id=block2.id,
        floor=1,
        capacity=40,
        room_type=RoomType.CLASSROOM,
        status=RoomStatus.ACTIVE,
        facilities=[],
    )
    db_session.add_all([room1, room2, room_other])
    db_session.commit()

    return {
        "dept": dept,
        "block1": block1,
        "block2": block2,
        "coord": coord,
        "faculty": faculty,
        "slot1": slot1,
        "slot2": slot2,
        "room1": room1,
        "room2": room2,
        "room_other": room_other,
    }


def auth_header(user: User) -> dict:
    token = create_access_token(
        subject=user.id,
        extra_claims={"role": user.role.value, "email": user.email},
    )
    return {"Authorization": f"Bearer {token}"}


def test_coordinator_reject_requires_reason(client: TestClient, db_session: Session, dash_setup):
    coord = dash_setup["coord"]
    room1 = dash_setup["room1"]
    slot1 = dash_setup["slot1"]
    dept = dash_setup["dept"]

    headers = auth_header(coord)

    bk = Booking(
        reference="BK-TEST-REJ",
        room_id=room1.id,
        date=date.today() + timedelta(days=2),
        slot_id=slot1.id,
        purpose="Guest Lecture",
        expected_strength=40,
        status=BookingStatus.PENDING,
        requester_type=RequesterType.STUDENT,
        roll_no="ST-01",
        name="Alice",
        email="alice@college.edu",
        department_id=dept.id,
        phone="9876543210",
    )
    db_session.add(bk)
    db_session.commit()

    # Reject without note should fail (400)
    res = client.post(
        f"/api/coordinator/bookings/{bk.id}/decision",
        json={"action": "reject", "note": ""},
        headers=headers,
    )
    assert res.status_code == 400
    assert "Rejection reason is required" in res.json()["detail"]

    # Reject with note should succeed
    res2 = client.post(
        f"/api/coordinator/bookings/{bk.id}/decision",
        json={"action": "reject", "note": "Classroom needed for department event"},
        headers=headers,
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "REJECTED"



def test_coordinator_bulk_approve(client: TestClient, db_session: Session, dash_setup):
    coord = dash_setup["coord"]
    room1 = dash_setup["room1"]
    room2 = dash_setup["room2"]
    slot1 = dash_setup["slot1"]
    dept = dash_setup["dept"]

    headers = auth_header(coord)

    tomorrow = date.today() + timedelta(days=1)
    b1 = Booking(
        reference="BK-B1",
        room_id=room1.id,
        date=tomorrow,
        slot_id=slot1.id,
        purpose="Session 1",
        expected_strength=30,
        status=BookingStatus.PENDING,
        requester_type=RequesterType.STUDENT,
        name="Student 1",
        email="s1@college.edu",
        department_id=dept.id,
        phone="9876543210",
    )
    b2 = Booking(
        reference="BK-B2",
        room_id=room2.id,
        date=tomorrow,
        slot_id=slot1.id,
        purpose="Session 2",
        expected_strength=35,
        status=BookingStatus.PENDING,
        requester_type=RequesterType.STUDENT,
        name="Student 2",
        email="s2@college.edu",
        department_id=dept.id,
        phone="9876543210",
    )
    db_session.add_all([b1, b2])
    db_session.commit()

    res = client.post(
        "/api/coordinator/bookings/bulk-decision",
        json={"booking_ids": [b1.id, b2.id], "action": "approve"},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success_count"] == 2
    assert len(data["processed_ids"]) == 2

    db_session.refresh(b1)
    db_session.refresh(b2)
    assert b1.status == BookingStatus.APPROVED
    assert b2.status == BookingStatus.APPROVED


def test_room_block_preview_and_confirm_relocation(client: TestClient, db_session: Session, dash_setup):
    coord = dash_setup["coord"]
    room1 = dash_setup["room1"]
    room2 = dash_setup["room2"]
    slot1 = dash_setup["slot1"]
    dept = dash_setup["dept"]

    headers = auth_header(coord)

    target_date = date.today() + timedelta(days=3)
    bk = Booking(
        reference="BK-RELOC",
        room_id=room1.id,
        date=target_date,
        slot_id=slot1.id,
        purpose="Seminar",
        expected_strength=40,
        status=BookingStatus.APPROVED,
        requester_type=RequesterType.STUDENT,
        name="Seminar Lead",
        email="lead@college.edu",
        department_id=dept.id,
        phone="9876543210",
    )
    db_session.add(bk)
    db_session.commit()

    # 1. Preview
    res_preview = client.post(
        "/api/coordinator/room-blocks/preview",
        json={
            "room_id": room1.id,
            "date_from": str(target_date),
            "date_to": str(target_date),
            "reason": "MAINTENANCE",
        },
        headers=headers,
    )
    assert res_preview.status_code == 200
    pdata = res_preview.json()
    assert pdata["total_affected"] == 1
    assert pdata["can_relocate_count"] == 1
    assert pdata["affected_bookings"][0]["suggested_room_id"] == room2.id

    # 2. Confirm relocation
    res_confirm = client.post(
        "/api/coordinator/room-blocks/confirm-relocation",
        json={
            "room_id": room1.id,
            "date_from": str(target_date),
            "date_to": str(target_date),
            "reason": "MAINTENANCE",
            "note": "A/C repairs",
        },
        headers=headers,
    )
    assert res_confirm.status_code == 201
    cdata = res_confirm.json()
    assert cdata["blocks_created"] >= 1
    assert cdata["relocated_count"] == 1

    db_session.refresh(bk)
    assert bk.status == BookingStatus.RELOCATED
    assert bk.room_id == room2.id


def test_faculty_endpoints(client: TestClient, db_session: Session, dash_setup):
    faculty = dash_setup["faculty"]
    room1 = dash_setup["room1"]
    slot1 = dash_setup["slot1"]

    headers = auth_header(faculty)

    target_date = date.today() + timedelta(days=4)

    # 1. Create booking
    res_create = client.post(
        "/api/faculty/bookings",
        json={
            "room_id": room1.id,
            "date": str(target_date),
            "slot_id": slot1.id,
            "purpose": "Advanced Algorithms Lecture",
            "expected_strength": 45,
            "faculty_id": "FAC-TUR",
            "class_name": "CS IV Year",
        },
        headers=headers,
    )
    assert res_create.status_code == 201
    b_data = res_create.json()
    assert b_data["status"] == "PENDING"
    assert b_data["roll_no"] == "FAC-TUR"
    b_id = b_data["id"]

    # 2. Pending count
    res_count = client.get("/api/faculty/bookings/pending-count", headers=headers)
    assert res_count.status_code == 200
    assert res_count.json()["pending_count"] >= 1

    # 3. List bookings
    res_list = client.get("/api/faculty/bookings", headers=headers)
    assert res_list.status_code == 200
    assert res_list.json()["total"] >= 1

    # 4. Cancel booking
    res_cancel = client.post(f"/api/faculty/bookings/{b_id}/cancel", headers=headers)
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "CANCELLED"

    # 5. Search availability as faculty
    res_avail = client.get(
        f"/api/faculty/availability?date={target_date}&slot_ids={slot1.id}&min_capacity=40",
        headers=headers,
    )
    assert res_avail.status_code == 200
    avail_data = res_avail.json()
    assert avail_data["total_available"] >= 1
    assert len(avail_data["available_rooms"]) >= 1


def test_coordinator_blocks_route(client: TestClient, db_session: Session, dash_setup):
    coord = dash_setup["coord"]
    block1 = dash_setup["block1"]
    headers = auth_header(coord)

    res = client.get("/api/coordinator/blocks", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["total"] == 1
    assert data["items"][0]["id"] == block1.id
    assert data["items"][0]["name"] == block1.name


def test_coordinator_rooms_route(client: TestClient, db_session: Session, dash_setup):
    coord = dash_setup["coord"]
    block1 = dash_setup["block1"]
    room1 = dash_setup["room1"]
    room2 = dash_setup["room2"]
    headers = auth_header(coord)

    # 1. Fetch all rooms in coordinator's assigned blocks
    res = client.get("/api/coordinator/rooms", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["total"] == 2
    room_ids = [r["id"] for r in data["items"]]
    assert room1.id in room_ids
    assert room2.id in room_ids

    # Verify response schema fields: id, name, block, floor, room_type, capacity, status
    first_room = data["items"][0]
    for field in ["id", "name", "block", "block_id", "floor", "room_type", "capacity", "status"]:
        assert field in first_room

    # 2. Filter by block_id
    res_b = client.get(f"/api/coordinator/rooms?block_id={block1.id}", headers=headers)
    assert res_b.status_code == 200
    assert res_b.json()["total"] == 2

    # 3. Filter by search
    res_s = client.get("/api/coordinator/rooms?search=C-101", headers=headers)
    assert res_s.status_code == 200
    assert res_s.json()["total"] == 1
    assert res_s.json()["items"][0]["name"] == "C-101"


def test_coordinator_cannot_access_or_block_unassigned_block(client: TestClient, db_session: Session, dash_setup):
    coord = dash_setup["coord"]
    block2 = dash_setup["block2"]
    room_other = dash_setup["room_other"]
    headers = auth_header(coord)

    target_date = date.today() + timedelta(days=5)

    # 1. Accessing rooms with an unassigned block_id should return 403 Forbidden
    res_rooms = client.get(f"/api/coordinator/rooms?block_id={block2.id}", headers=headers)
    assert res_rooms.status_code == 403

    # 2. Previewing a room block on unassigned block's room should return 403 Forbidden
    res_preview = client.post(
        "/api/coordinator/room-blocks/preview",
        json={
            "room_id": room_other.id,
            "date_from": str(target_date),
            "date_to": str(target_date),
            "reason": "MAINTENANCE",
        },
        headers=headers,
    )
    assert res_preview.status_code == 403

    # 3. Creating a room block on unassigned block's room should return 403 Forbidden
    res_block = client.post(
        "/api/coordinator/room-blocks",
        json={
            "room_id": room_other.id,
            "date_from": str(target_date),
            "date_to": str(target_date),
            "reason": "MAINTENANCE",
        },
        headers=headers,
    )
    assert res_block.status_code == 403

    # 4. Confirming relocation on unassigned block's room should return 403 Forbidden
    res_confirm = client.post(
        "/api/coordinator/room-blocks/confirm-relocation",
        json={
            "room_id": room_other.id,
            "date_from": str(target_date),
            "date_to": str(target_date),
            "reason": "MAINTENANCE",
        },
        headers=headers,
    )
    assert res_confirm.status_code == 403


def test_coordinator_block_room_timetable_verification(client: TestClient, db_session: Session, dash_setup):
    coord = dash_setup["coord"]
    block1 = dash_setup["block1"]
    room1 = dash_setup["room1"]
    slot1 = dash_setup["slot1"]
    headers = auth_header(coord)

    target_date = date.today() + timedelta(days=6)

    # Block room1 for slot1 with reason MAINTENANCE
    res_create = client.post(
        "/api/coordinator/room-blocks",
        json={
            "room_id": room1.id,
            "date_from": str(target_date),
            "date_to": str(target_date),
            "slot_ids": [slot1.id],
            "reason": "MAINTENANCE",
            "note": "HVAC servicing",
        },
        headers=headers,
    )
    assert res_create.status_code == 201
    assert res_create.json()["created_count"] == 1

    # Check timetable grid shows room1 in MAINTENANCE for that slot
    res_tt = client.get(
        f"/api/coordinator/timetable?date={target_date}&block_id={block1.id}",
        headers=headers,
    )
    assert res_tt.status_code == 200
    tt_data = res_tt.json()
    assert "grid" in tt_data

    # Grid mapping is room_id string -> slot_id string -> cell status
    assert str(room1.id) in tt_data["grid"]
    slot_status = tt_data["grid"][str(room1.id)].get(str(slot1.id))
    assert slot_status == "MAINTENANCE"



