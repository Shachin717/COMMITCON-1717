from datetime import date, time, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.block import Block, BlockCoordinator
from app.models.department import Department
from app.models.enums import RoomBlockReason, RoomStatus, RoomType, UserRole
from app.models.room import Room
from app.models.room_block import RoomBlock
from app.models.time_slot import TimeSlot
from app.models.user import User


@pytest.fixture
def blocks_setup(db_session: Session):
    pwd = hash_password("Secret123!")

    dept = Department(name="Computer Science", code="CS", hod_approval_required=False)
    block_a = Block(name="Block A", description="Engineering Wing")
    block_b = Block(name="Block B", description="Science Wing")
    db_session.add_all([dept, block_a, block_b])
    db_session.flush()

    coord_a = User(
        name="Coordinator A",
        email="coord_a@college.edu",
        password_hash=pwd,
        role=UserRole.COORDINATOR,
        is_active=True,
    )
    coord_b = User(
        name="Coordinator B",
        email="coord_b@college.edu",
        password_hash=pwd,
        role=UserRole.COORDINATOR,
        is_active=True,
    )
    admin = User(
        name="Admin User",
        email="admin@college.edu",
        password_hash=pwd,
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add_all([coord_a, coord_b, admin])
    db_session.flush()

    db_session.add(BlockCoordinator(block_id=block_a.id, user_id=coord_a.id))
    db_session.add(BlockCoordinator(block_id=block_b.id, user_id=coord_b.id))

    slot1 = TimeSlot(label="Period 1", start_time=time(9, 0), end_time=time(10, 0), order=1)
    slot2 = TimeSlot(label="Period 2", start_time=time(10, 0), end_time=time(11, 0), order=2)
    db_session.add_all([slot1, slot2])
    db_session.flush()

    room_a1 = Room(
        name="A-101",
        block_id=block_a.id,
        floor=1,
        capacity=60,
        room_type=RoomType.CLASSROOM,
        status=RoomStatus.ACTIVE,
    )
    room_a2 = Room(
        name="A-102",
        block_id=block_a.id,
        floor=1,
        capacity=40,
        room_type=RoomType.CLASSROOM,
        status=RoomStatus.ACTIVE,
    )
    room_b1 = Room(
        name="B-101",
        block_id=block_b.id,
        floor=1,
        capacity=50,
        room_type=RoomType.CLASSROOM,
        status=RoomStatus.ACTIVE,
    )
    db_session.add_all([room_a1, room_a2, room_b1])
    db_session.commit()

    return {
        "coord_a": coord_a,
        "coord_b": coord_b,
        "admin": admin,
        "block_a": block_a,
        "block_b": block_b,
        "room_a1": room_a1,
        "room_a2": room_a2,
        "room_b1": room_b1,
        "slot1": slot1,
        "slot2": slot2,
    }


def auth_header(user: User):
    token = create_access_token(
        subject=user.id,
        extra_claims={"role": user.role.value, "email": user.email},
    )
    return {"Authorization": f"Bearer {token}"}


def test_list_blocked_rooms_and_indefinite_maintenance(client: TestClient, db_session: Session, blocks_setup):
    headers = auth_header(blocks_setup["coord_a"])
    today = date.today()
    tomorrow = today + timedelta(days=1)

    # 1. Create a block for tomorrow
    rb_tomorrow = RoomBlock(
        room_id=blocks_setup["room_a1"].id,
        date=tomorrow,
        slot_id=blocks_setup["slot1"].id,
        reason=RoomBlockReason.MAINTENANCE,
        note="AC Duct cleaning",
        created_by=blocks_setup["coord_a"].id,
    )
    # 2. Set room_a2 to indefinite MAINTENANCE in catalog
    blocks_setup["room_a2"].status = RoomStatus.MAINTENANCE
    blocks_setup["room_a2"].maintenance_note = "Projector replacement"
    db_session.add(rb_tomorrow)
    db_session.add(blocks_setup["room_a2"])
    db_session.commit()

    # Query room blocks
    res = client.get("/api/coordinator/room-blocks", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "items" in data
    assert "summary" in data

    # Summary strip checks
    assert data["summary"]["currently_blocked"] >= 1  # room_a2
    assert data["summary"]["upcoming_blocks"] >= 1  # rb_tomorrow

    # Check items contains both tomorrow's block and indefinite maintenance
    names = [item["room"]["name"] for item in data["items"]]
    assert "A-101" in names
    assert "A-201" not in names
    assert "A-102" in names

    # Filter status=upcoming
    res_upcoming = client.get("/api/coordinator/room-blocks?status=upcoming", headers=headers)
    assert res_upcoming.status_code == 200
    upcoming_data = res_upcoming.json()
    assert all(item["status"] == "UPCOMING" for item in upcoming_data["items"])


def test_create_overlapping_block_returns_400(client: TestClient, db_session: Session, blocks_setup):
    headers = auth_header(blocks_setup["coord_a"])
    target_date = date.today() + timedelta(days=2)

    # Create first block
    payload1 = {
        "room_id": blocks_setup["room_a1"].id,
        "date_from": str(target_date),
        "date_to": str(target_date),
        "slot_ids": [blocks_setup["slot1"].id],
        "reason": "MAINTENANCE",
        "note": "Floor polishing",
    }
    r1 = client.post("/api/coordinator/room-blocks", json=payload1, headers=headers)
    assert r1.status_code == 201, r1.text

    # Attempt to create overlapping block for same room, date, and slot
    payload2 = {
        "room_id": blocks_setup["room_a1"].id,
        "date_from": str(target_date),
        "date_to": str(target_date),
        "slot_ids": [blocks_setup["slot1"].id],
        "reason": "EXAM",
        "note": "Midterm exam",
    }
    r2 = client.post("/api/coordinator/room-blocks", json=payload2, headers=headers)
    assert r2.status_code == 400
    assert "already blocked" in r2.json()["detail"]


def test_release_single_block_and_availability_restoration(client: TestClient, db_session: Session, blocks_setup):
    headers = auth_header(blocks_setup["coord_a"])
    target_date = date.today() + timedelta(days=3)

    # Create block
    payload = {
        "room_id": blocks_setup["room_a1"].id,
        "date_from": str(target_date),
        "date_to": str(target_date),
        "slot_ids": [blocks_setup["slot1"].id],
        "reason": "MAINTENANCE",
        "note": "Electrical work",
    }
    res_create = client.post("/api/coordinator/room-blocks", json=payload, headers=headers)
    assert res_create.status_code == 201
    created_id = res_create.json()["blocks"][0]["id"]

    # Verify room is NOT available via public availability search
    res_avail1 = client.get(
        f"/api/public/availability?date={target_date}&slot_ids={blocks_setup['slot1'].id}&block_id={blocks_setup['block_a'].id}"
    )
    assert res_avail1.status_code == 200
    avail_rooms_1 = [r["id"] for r in res_avail1.json()["available_rooms"]]
    assert blocks_setup["room_a1"].id not in avail_rooms_1

    # Release the block
    res_release = client.post(f"/api/coordinator/room-blocks/{created_id}/release", headers=headers)
    assert res_release.status_code == 200, res_release.text
    assert res_release.json()["is_released"] is True

    # Verify room is NOW AVAILABLE immediately
    res_avail2 = client.get(
        f"/api/public/availability?date={target_date}&slot_ids={blocks_setup['slot1'].id}&block_id={blocks_setup['block_a'].id}"
    )
    assert res_avail2.status_code == 200
    avail_rooms_2 = [r["id"] for r in res_avail2.json()["available_rooms"]]
    assert blocks_setup["room_a1"].id in avail_rooms_2


def test_bulk_release_room_blocks(client: TestClient, db_session: Session, blocks_setup):
    headers = auth_header(blocks_setup["coord_a"])
    d1 = date.today() + timedelta(days=4)
    d2 = date.today() + timedelta(days=5)

    # Create two blocks
    res_create = client.post(
        "/api/coordinator/room-blocks",
        json={
            "room_id": blocks_setup["room_a1"].id,
            "date_from": str(d1),
            "date_to": str(d2),
            "slot_ids": [blocks_setup["slot1"].id],
            "reason": "MAINTENANCE",
            "note": "Painting",
        },
        headers=headers,
    )
    assert res_create.status_code == 201
    block_ids = [b["id"] for b in res_create.json()["blocks"]]
    assert len(block_ids) == 2

    # Bulk release by IDs
    res_bulk = client.post(
        "/api/coordinator/room-blocks/release-bulk",
        json={"ids": block_ids},
        headers=headers,
    )
    assert res_bulk.status_code == 200
    assert res_bulk.json()["released_count"] == 2
    assert set(res_bulk.json()["released_ids"]) == set(block_ids)


def test_permission_coordinator_cannot_release_other_block(client: TestClient, db_session: Session, blocks_setup):
    headers_b = auth_header(blocks_setup["coord_b"])
    target_date = date.today() + timedelta(days=6)

    # Coordinator A blocks room in Block A
    rb = RoomBlock(
        room_id=blocks_setup["room_a1"].id,
        date=target_date,
        slot_id=blocks_setup["slot1"].id,
        reason=RoomBlockReason.MAINTENANCE,
        created_by=blocks_setup["coord_a"].id,
    )
    db_session.add(rb)
    db_session.commit()
    db_session.refresh(rb)

    # Coordinator B tries to release Coordinator A's room block (must be 403)
    res = client.post(f"/api/coordinator/room-blocks/{rb.id}/release", headers=headers_b)
    assert res.status_code == 403
    assert "Access forbidden" in res.json()["detail"]


def test_release_past_block_returns_400(client: TestClient, db_session: Session, blocks_setup):
    headers = auth_header(blocks_setup["coord_a"])
    past_date = date.today() - timedelta(days=2)

    rb = RoomBlock(
        room_id=blocks_setup["room_a1"].id,
        date=past_date,
        slot_id=blocks_setup["slot1"].id,
        reason=RoomBlockReason.MAINTENANCE,
        created_by=blocks_setup["coord_a"].id,
    )
    db_session.add(rb)
    db_session.commit()
    db_session.refresh(rb)

    res = client.post(f"/api/coordinator/room-blocks/{rb.id}/release", headers=headers)
    assert res.status_code == 400
    assert "already completely passed" in res.json()["detail"]


def test_release_room_maintenance_endpoint(client: TestClient, db_session: Session, blocks_setup):
    headers_a = auth_header(blocks_setup["coord_a"])
    headers_b = auth_header(blocks_setup["coord_b"])

    # Set room_a1 to MAINTENANCE
    blocks_setup["room_a1"].status = RoomStatus.MAINTENANCE
    blocks_setup["room_a1"].maintenance_note = "Deep clean"
    db_session.commit()

    # Coordinator B cannot release maintenance on room A1 (403)
    r_bad = client.post(f"/api/coordinator/rooms/{blocks_setup['room_a1'].id}/release-maintenance", headers=headers_b)
    assert r_bad.status_code == 403

    # Coordinator A can release maintenance
    r_ok = client.post(f"/api/coordinator/rooms/{blocks_setup['room_a1'].id}/release-maintenance", headers=headers_a)
    assert r_ok.status_code == 200
    data = r_ok.json()
    assert data["status"] == "ACTIVE"

    # Verify room is now ACTIVE in db
    db_session.refresh(blocks_setup["room_a1"])
    assert blocks_setup["room_a1"].status == RoomStatus.ACTIVE
    assert blocks_setup["room_a1"].maintenance_note is None
