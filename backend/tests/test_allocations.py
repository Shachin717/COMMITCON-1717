import pytest
from datetime import date, time, datetime, timedelta
from fastapi.testclient import TestClient
from app.optimizer.result_validator import AllocationResultValidator
from app.optimizer.constraints import SessionData, RoomData, TimeBlock


def test_reject_overlapping_sessions_for_same_class_group(client: TestClient):
    dept = client.post("/api/v1/departments", json={"name": "CS Dept", "code": "CSD"}).json()
    group = client.post(
        "/api/v1/class-groups",
        json={"name": "Year 1 CS", "department_id": dept["id"], "student_count": 40},
    ).json()

    # First session: 09:00 to 11:00
    s1 = client.post(
        "/api/v1/class-sessions",
        json={
            "class_group_id": group["id"],
            "session_date": "2026-10-21",
            "start_time": "09:00:00",
            "end_time": "11:00:00",
            "required_room_type": "CLASSROOM",
        },
    )
    assert s1.status_code == 201

    # Overlapping session for same class group: 10:00 to 12:00
    s2 = client.post(
        "/api/v1/class-sessions",
        json={
            "class_group_id": group["id"],
            "session_date": "2026-10-21",
            "start_time": "10:00:00",
            "end_time": "12:00:00",
            "required_room_type": "CLASSROOM",
        },
    )
    assert s2.status_code == 409


def test_generate_valid_optimized_allocation_and_validate_hard_constraints(client: TestClient):
    dept = client.post("/api/v1/departments", json={"name": "IT Dept", "code": "ITD"}).json()
    group1 = client.post(
        "/api/v1/class-groups",
        json={"name": "IT Sec A", "department_id": dept["id"], "student_count": 35},
    ).json()
    group2 = client.post(
        "/api/v1/class-groups",
        json={"name": "IT Sec B", "department_id": dept["id"], "student_count": 55},
    ).json()

    # Create two rooms: Room A (cap 40), Room B (cap 60)
    r_a = client.post(
        "/api/v1/classrooms",
        json={"name": "Room A 40", "capacity": 40, "room_type": "CLASSROOM"},
    ).json()
    r_b = client.post(
        "/api/v1/classrooms",
        json={"name": "Room B 60", "capacity": 60, "room_type": "CLASSROOM"},
    ).json()

    # Two concurrent sessions: 09:00 to 10:30
    s1 = client.post(
        "/api/v1/class-sessions",
        json={
            "class_group_id": group1["id"],
            "session_date": "2026-10-22",
            "start_time": "09:00:00",
            "end_time": "10:30:00",
            "required_room_type": "CLASSROOM",
        },
    ).json()
    s2 = client.post(
        "/api/v1/class-sessions",
        json={
            "class_group_id": group2["id"],
            "session_date": "2026-10-22",
            "start_time": "09:00:00",
            "end_time": "10:30:00",
            "required_room_type": "CLASSROOM",
        },
    ).json()

    # Generate Allocation
    resp = client.post(
        "/api/v1/allocations/generate",
        json={
            "start_date": "2026-10-22",
            "end_date": "2026-10-22",
            "session_ids": [s1["id"], s2["id"]],
        },
    )
    assert resp.status_code == 201
    run = resp.json()
    assert run["status"] == "OPTIMAL"
    assert run["allocated_sessions"] == 2
    assert run["unallocated_sessions"] == 0

    alloc_map = {a["class_session_id"]: a["room_id"] for a in run["allocations"]}
    # Group 1 (35 students) -> Room A (40 seats)
    # Group 2 (55 students) -> Room B (60 seats)
    assert alloc_map[s1["id"]] == r_a["id"]
    assert alloc_map[s2["id"]] == r_b["id"]

    # Explicitly test AllocationResultValidator on the generated allocation
    sess_obj_1 = SessionData(
        id=s1["id"],
        class_group_id=group1["id"],
        department_id=dept["id"],
        student_count=35,
        session_date=date(2026, 10, 22),
        start_time=time(9, 0),
        end_time=time(10, 30),
        required_room_type="CLASSROOM",
    )
    sess_obj_2 = SessionData(
        id=s2["id"],
        class_group_id=group2["id"],
        department_id=dept["id"],
        student_count=55,
        session_date=date(2026, 10, 22),
        start_time=time(9, 0),
        end_time=time(10, 30),
        required_room_type="CLASSROOM",
    )
    room_obj_a = RoomData(
        id=r_a["id"], name="Room A 40", capacity=40, room_type="CLASSROOM", building_id=None, is_active=True
    )
    room_obj_b = RoomData(
        id=r_b["id"], name="Room B 60", capacity=60, room_type="CLASSROOM", building_id=None, is_active=True
    )

    violations = AllocationResultValidator.validate(
        allocations=alloc_map,
        sessions={s1["id"]: sess_obj_1, s2["id"]: sess_obj_2},
        rooms={r_a["id"]: room_obj_a, r_b["id"]: room_obj_b},
        room_unavailabilities={},
        confirmed_bookings={},
        published_allocations={},
    )
    assert len(violations) == 0, f"Validator found violations: {violations}"

    # Publish draft allocation
    pub_resp = client.post(f"/api/v1/allocations/{run['id']}/publish")
    assert pub_resp.status_code == 200
    for a in pub_resp.json()["allocations"]:
        assert a["status"] == "PUBLISHED"


def test_report_unallocated_sessions_when_insufficient_rooms(client: TestClient):
    dept = client.post("/api/v1/departments", json={"name": "Civil Dept", "code": "CIV"}).json()
    group1 = client.post(
        "/api/v1/class-groups",
        json={"name": "Civ Sec 1", "department_id": dept["id"], "student_count": 30},
    ).json()
    group2 = client.post(
        "/api/v1/class-groups",
        json={"name": "Civ Sec 2", "department_id": dept["id"], "student_count": 30},
    ).json()

    # Only ONE eligible room
    client.post(
        "/api/v1/classrooms",
        json={"name": "Only Single Room", "capacity": 40, "room_type": "CLASSROOM"},
    )

    # Two concurrent sessions
    s1 = client.post(
        "/api/v1/class-sessions",
        json={
            "class_group_id": group1["id"],
            "session_date": "2026-10-23",
            "start_time": "14:00:00",
            "end_time": "15:30:00",
            "required_room_type": "CLASSROOM",
        },
    ).json()
    s2 = client.post(
        "/api/v1/class-sessions",
        json={
            "class_group_id": group2["id"],
            "session_date": "2026-10-23",
            "start_time": "14:00:00",
            "end_time": "15:30:00",
            "required_room_type": "CLASSROOM",
        },
    ).json()

    # Run allocation
    resp = client.post(
        "/api/v1/allocations/generate",
        json={"session_ids": [s1["id"], s2["id"]]},
    )
    assert resp.status_code == 201
    run = resp.json()
    # 1 session must be allocated and 1 must be reported unallocated
    assert run["allocated_sessions"] == 1
    assert run["unallocated_sessions"] == 1
    assert len(run["unallocated_session_ids"]) == 1


def test_reallocate_after_room_becomes_unavailable_and_preserve_unaffected(client: TestClient):
    dept = client.post("/api/v1/departments", json={"name": "Physics Dept", "code": "PHY"}).json()
    g1 = client.post(
        "/api/v1/class-groups",
        json={"name": "Phys 1", "department_id": dept["id"], "student_count": 30},
    ).json()
    g2 = client.post(
        "/api/v1/class-groups",
        json={"name": "Phys 2", "department_id": dept["id"], "student_count": 30},
    ).json()

    r1 = client.post(
        "/api/v1/classrooms",
        json={"name": "Lab Hall 1", "capacity": 50, "room_type": "CLASSROOM"},
    ).json()
    r2 = client.post(
        "/api/v1/classrooms",
        json={"name": "Lab Hall 2", "capacity": 50, "room_type": "CLASSROOM"},
    ).json()
    r3 = client.post(
        "/api/v1/classrooms",
        json={"name": "Lab Hall 3 (Backup)", "capacity": 50, "room_type": "CLASSROOM"},
    ).json()

    s1 = client.post(
        "/api/v1/class-sessions",
        json={
            "class_group_id": g1["id"],
            "session_date": "2026-10-24",
            "start_time": "09:00:00",
            "end_time": "10:30:00",
            "required_room_type": "CLASSROOM",
        },
    ).json()
    s2 = client.post(
        "/api/v1/class-sessions",
        json={
            "class_group_id": g2["id"],
            "session_date": "2026-10-24",
            "start_time": "09:00:00",
            "end_time": "10:30:00",
            "required_room_type": "CLASSROOM",
        },
    ).json()

    # Initial allocation
    gen_resp = client.post(
        "/api/v1/allocations/generate",
        json={"session_ids": [s1["id"], s2["id"]]},
    ).json()
    run_id = gen_resp["id"]

    alloc_map_before = {a["class_session_id"]: a["room_id"] for a in gen_resp["allocations"]}
    assigned_r_for_s1 = alloc_map_before[s1["id"]]
    assigned_r_for_s2 = alloc_map_before[s2["id"]]

    # Now make ONLY the room assigned to s1 unavailable (maintenance)
    client.post(
        "/api/v1/room-unavailability",
        json={
            "room_id": assigned_r_for_s1,
            "start_datetime": "2026-10-24T08:00:00",
            "end_datetime": "2026-10-24T12:00:00",
            "reason": "Emergency roof repairs",
            "force": True,
        },
    )

    # Reoptimize
    reopt_resp = client.post(f"/api/v1/allocations/{run_id}/reoptimize")
    assert reopt_resp.status_code == 200
    summary = reopt_resp.json()
    new_run = summary["allocation_run"]

    new_alloc_map = {a["class_session_id"]: a["room_id"] for a in new_run["allocations"]}
    # 1. The session that lost its room was moved away from the unavailable room
    assert new_alloc_map[s1["id"]] != assigned_r_for_s1
    # 2. Unaffected assignment for s2 was preserved in the same room!
    assert new_alloc_map[s2["id"]] == assigned_r_for_s2
    assert summary["retained_count"] >= 1


def test_reject_publishing_stale_or_conflicting_draft(client: TestClient):
    dept = client.post("/api/v1/departments", json={"name": "Chemistry", "code": "CHM"}).json()
    group = client.post(
        "/api/v1/class-groups",
        json={"name": "Chem Sec", "department_id": dept["id"], "student_count": 30},
    ).json()
    room = client.post(
        "/api/v1/classrooms",
        json={"name": "Chem Room", "capacity": 50, "room_type": "CLASSROOM"},
    ).json()

    sess = client.post(
        "/api/v1/class-sessions",
        json={
            "class_group_id": group["id"],
            "session_date": "2026-10-25",
            "start_time": "10:00:00",
            "end_time": "11:30:00",
            "required_room_type": "CLASSROOM",
        },
    ).json()

    # Generate draft allocation
    run = client.post(
        "/api/v1/allocations/generate",
        json={"session_ids": [sess["id"]]},
    ).json()

    # In the meantime, an admin books the room for an urgent campus event at the same time
    client.post(
        "/api/v1/bookings",
        json={
            "room_id": room["id"],
            "title": "Urgent Campus Board Meeting",
            "start_datetime": "2026-10-25T10:00:00",
            "end_datetime": "2026-10-25T11:30:00",
            "status": "CONFIRMED",
        },
    )

    # Attempting to publish the draft should now fail with HTTP 409 Conflict because of stale conditions!
    pub_resp = client.post(f"/api/v1/allocations/{run['id']}/publish")
    assert pub_resp.status_code == 409

