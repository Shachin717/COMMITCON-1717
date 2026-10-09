import pytest
from fastapi.testclient import TestClient


def test_create_and_retrieve_classroom(client: TestClient):
    # 1. Create a classroom
    response = client.post(
        "/api/v1/classrooms",
        json={
            "name": "Hall 101",
            "capacity": 50,
            "room_type": "CLASSROOM",
            "location_description": "First Floor East Wing",
            "is_active": True,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Hall 101"
    assert data["capacity"] == 50
    assert data["room_type"] == "CLASSROOM"
    room_id = data["id"]

    # 2. Retrieve classroom
    get_resp = client.get(f"/api/v1/classrooms/{room_id}")
    assert get_resp.status_code == 200
    retrieved = get_resp.json()
    assert retrieved["id"] == room_id
    assert retrieved["name"] == "Hall 101"


def test_reject_zero_or_negative_capacity(client: TestClient):
    # Zero capacity
    resp_zero = client.post(
        "/api/v1/classrooms",
        json={"name": "Bad Room 0", "capacity": 0, "room_type": "CLASSROOM"},
    )
    assert resp_zero.status_code == 422

    # Negative capacity
    resp_neg = client.post(
        "/api/v1/classrooms",
        json={"name": "Bad Room Neg", "capacity": -10, "room_type": "CLASSROOM"},
    )
    assert resp_neg.status_code == 422


def test_regular_classroom_shared_across_all_departments(client: TestClient):
    # Create two departments
    d1 = client.post("/api/v1/departments", json={"name": "Computer Science", "code": "CS"}).json()
    d2 = client.post("/api/v1/departments", json={"name": "Mechanical", "code": "ME"}).json()

    # Create regular classroom
    room = client.post(
        "/api/v1/classrooms",
        json={"name": "Shared Room A", "capacity": 60, "room_type": "CLASSROOM"},
    ).json()

    # Regular classroom should have no department restrictions in availability
    avail_d1 = client.get(
        "/api/v1/availability",
        params={
            "start_datetime": "2026-10-15T09:00:00",
            "end_datetime": "2026-10-15T10:00:00",
            "department_id": d1["id"],
            "student_count": 50,
        },
    ).json()
    eligible_ids_1 = [r["id"] for r in avail_d1["eligible_rooms"]]
    assert room["id"] in eligible_ids_1

    avail_d2 = client.get(
        "/api/v1/availability",
        params={
            "start_datetime": "2026-10-15T09:00:00",
            "end_datetime": "2026-10-15T10:00:00",
            "department_id": d2["id"],
            "student_count": 50,
        },
    ).json()
    eligible_ids_2 = [r["id"] for r in avail_d2["eligible_rooms"]]
    assert room["id"] in eligible_ids_2

    # Attempting to assign department access to a regular classroom must be rejected (422)
    resp = client.put(
        f"/api/v1/classrooms/{room['id']}/department-access",
        json={"department_ids": [d1["id"]]},
    )
    assert resp.status_code == 422

