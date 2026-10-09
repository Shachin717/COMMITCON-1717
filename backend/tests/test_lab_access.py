import pytest
from fastapi.testclient import TestClient


def test_reject_lab_for_unauthorized_department(client: TestClient):
    # Create Departments CSE and ECE
    dept_cse = client.post("/api/v1/departments", json={"name": "CSE", "code": "CSE"}).json()
    dept_ece = client.post("/api/v1/departments", json={"name": "ECE", "code": "ECE"}).json()

    # Create a LAB
    lab = client.post(
        "/api/v1/classrooms",
        json={"name": "CSE Dedicated Lab", "capacity": 40, "room_type": "LAB"},
    ).json()

    # Authorize only CSE
    access_resp = client.put(
        f"/api/v1/classrooms/{lab['id']}/department-access",
        json={"department_ids": [dept_cse["id"]]},
    )
    assert access_resp.status_code == 200

    # Availability check for CSE: Lab should be eligible
    avail_cse = client.get(
        "/api/v1/availability",
        params={
            "start_datetime": "2026-10-15T10:00:00",
            "end_datetime": "2026-10-15T12:00:00",
            "department_id": dept_cse["id"],
            "room_type": "LAB",
            "student_count": 30,
        },
    ).json()
    eligible_cse_ids = [r["id"] for r in avail_cse["eligible_rooms"]]
    assert lab["id"] in eligible_cse_ids

    # Availability check for ECE: Lab MUST NOT be eligible
    avail_ece = client.get(
        "/api/v1/availability",
        params={
            "start_datetime": "2026-10-15T10:00:00",
            "end_datetime": "2026-10-15T12:00:00",
            "department_id": dept_ece["id"],
            "room_type": "LAB",
            "student_count": 30,
        },
    ).json()
    eligible_ece_ids = [r["id"] for r in avail_ece["eligible_rooms"]]
    assert lab["id"] not in eligible_ece_ids

    # Attempting to book the lab for unauthorized department ECE must be rejected
    booking_resp = client.post(
        "/api/v1/bookings",
        json={
            "room_id": lab["id"],
            "title": "Unauthorized ECE Lab Session",
            "department_id": dept_ece["id"],
            "start_datetime": "2026-10-15T10:00:00",
            "end_datetime": "2026-10-15T12:00:00",
        },
    )
    assert booking_resp.status_code == 422


def test_allow_multiple_authorized_departments_on_shared_lab(client: TestClient):
    dept_cse = client.post("/api/v1/departments", json={"name": "Computer Science", "code": "CS"}).json()
    dept_ece = client.post("/api/v1/departments", json={"name": "Electronics", "code": "EC"}).json()
    dept_mech = client.post("/api/v1/departments", json={"name": "Mechanical", "code": "ME"}).json()

    # Create Shared LAB
    shared_lab = client.post(
        "/api/v1/classrooms",
        json={"name": "Shared Computing Lab", "capacity": 50, "room_type": "LAB"},
    ).json()

    # Authorize CSE and ECE
    client.put(
        f"/api/v1/classrooms/{shared_lab['id']}/department-access",
        json={"department_ids": [dept_cse["id"], dept_ece["id"]]},
    )

    # Both CSE and ECE should see the lab as eligible
    avail_cse = client.get(
        "/api/v1/availability",
        params={
            "start_datetime": "2026-10-15T14:00:00",
            "end_datetime": "2026-10-15T16:00:00",
            "department_id": dept_cse["id"],
            "room_type": "LAB",
        },
    ).json()
    assert shared_lab["id"] in [r["id"] for r in avail_cse["eligible_rooms"]]

    avail_ece = client.get(
        "/api/v1/availability",
        params={
            "start_datetime": "2026-10-15T14:00:00",
            "end_datetime": "2026-10-15T16:00:00",
            "department_id": dept_ece["id"],
            "room_type": "LAB",
        },
    ).json()
    assert shared_lab["id"] in [r["id"] for r in avail_ece["eligible_rooms"]]

    # MECH should NOT see the lab as eligible
    avail_mech = client.get(
        "/api/v1/availability",
        params={
            "start_datetime": "2026-10-15T14:00:00",
            "end_datetime": "2026-10-15T16:00:00",
            "department_id": dept_mech["id"],
            "room_type": "LAB",
        },
    ).json()
    assert shared_lab["id"] not in [r["id"] for r in avail_mech["eligible_rooms"]]


def test_unconfigured_lab_is_restricted(client: TestClient):
    dept = client.post("/api/v1/departments", json={"name": "BioTech", "code": "BT"}).json()
    lab = client.post(
        "/api/v1/classrooms",
        json={"name": "Unconfigured Lab", "capacity": 30, "room_type": "LAB"},
    ).json()

    # With no authorized departments configured, it must NOT be available to any department
    avail = client.get(
        "/api/v1/availability",
        params={
            "start_datetime": "2026-10-15T09:00:00",
            "end_datetime": "2026-10-15T11:00:00",
            "department_id": dept["id"],
            "room_type": "LAB",
        },
    ).json()
    assert lab["id"] not in [r["id"] for r in avail["eligible_rooms"]]

