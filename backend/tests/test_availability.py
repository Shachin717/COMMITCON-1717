import pytest
from fastapi.testclient import TestClient


def test_availability_facility_and_capacity_matching(client: TestClient):
    # Create facilities
    proj = client.post("/api/v1/facilities", json={"name": "4K Projector"}).json()
    board = client.post("/api/v1/facilities", json={"name": "Interactive Board"}).json()

    # Room 1: Capacity 30, has Projector
    r1 = client.post(
        "/api/v1/classrooms",
        json={"name": "Room Small", "capacity": 30, "room_type": "CLASSROOM", "facility_ids": [proj["id"]]},
    ).json()

    # Room 2: Capacity 60, has Projector and Board
    r2 = client.post(
        "/api/v1/classrooms",
        json={
            "name": "Room Large",
            "capacity": 60,
            "room_type": "CLASSROOM",
            "facility_ids": [proj["id"], board["id"]],
        },
    ).json()

    # Room 3: Inactive
    client.post(
        "/api/v1/classrooms",
        json={"name": "Room Inactive", "capacity": 100, "room_type": "CLASSROOM", "is_active": False},
    )

    # 1. Query for 25 students, no specific facility -> both r1 and r2 eligible
    resp1 = client.get(
        "/api/v1/availability",
        params={
            "start_datetime": "2026-10-20T09:00:00",
            "end_datetime": "2026-10-20T10:00:00",
            "student_count": 25,
        },
    ).json()
    e_ids1 = [r["id"] for r in resp1["eligible_rooms"]]
    assert r1["id"] in e_ids1
    assert r2["id"] in e_ids1

    # 2. Query for 45 students -> only r2 eligible
    resp2 = client.get(
        "/api/v1/availability",
        params={
            "start_datetime": "2026-10-20T09:00:00",
            "end_datetime": "2026-10-20T10:00:00",
            "student_count": 45,
        },
    ).json()
    e_ids2 = [r["id"] for r in resp2["eligible_rooms"]]
    assert r1["id"] not in e_ids2
    assert r2["id"] in e_ids2

    # 3. Query for 25 students requiring Interactive Board -> only r2 has the board
    resp3 = client.get(
        "/api/v1/availability",
        params={
            "start_datetime": "2026-10-20T09:00:00",
            "end_datetime": "2026-10-20T10:00:00",
            "student_count": 25,
            "facility_ids": [board["id"]],
        },
    ).json()
    e_ids3 = [r["id"] for r in resp3["eligible_rooms"]]
    assert r1["id"] not in e_ids3
    assert r2["id"] in e_ids3

