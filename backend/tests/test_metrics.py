import pytest
from datetime import date, time
from fastapi.testclient import TestClient


def test_metrics_calculation_and_baseline_comparison(client: TestClient):
    dept = client.post("/api/v1/departments", json={"name": "Aero Dept", "code": "AER"}).json()

    # Create two groups: 30 students and 50 students
    g1 = client.post(
        "/api/v1/class-groups",
        json={"name": "Aero Year 1", "department_id": dept["id"], "student_count": 30},
    ).json()
    g2 = client.post(
        "/api/v1/class-groups",
        json={"name": "Aero Year 2", "department_id": dept["id"], "student_count": 50},
    ).json()

    # Create rooms: Room 1 (capacity 40), Room 2 (capacity 60)
    client.post(
        "/api/v1/classrooms",
        json={"name": "Aero Room 40", "capacity": 40, "room_type": "CLASSROOM"},
    )
    client.post(
        "/api/v1/classrooms",
        json={"name": "Aero Room 60", "capacity": 60, "room_type": "CLASSROOM"},
    )

    # Create two sessions at different non-overlapping times
    s1 = client.post(
        "/api/v1/class-sessions",
        json={
            "class_group_id": g1["id"],
            "session_date": "2026-10-26",
            "start_time": "09:00:00",
            "end_time": "10:30:00",
            "required_room_type": "CLASSROOM",
        },
    ).json()
    s2 = client.post(
        "/api/v1/class-sessions",
        json={
            "class_group_id": g2["id"],
            "session_date": "2026-10-26",
            "start_time": "11:00:00",
            "end_time": "12:30:00",
            "required_room_type": "CLASSROOM",
        },
    ).json()

    # Generate allocation
    run = client.post(
        "/api/v1/allocations/generate",
        json={"session_ids": [s1["id"], s2["id"]]},
    ).json()

    # Retrieve metrics
    metrics_resp = client.get(f"/api/v1/allocations/{run['id']}/metrics")
    assert metrics_resp.status_code == 200
    metrics_data = metrics_resp.json()

    assert "optimizer_metrics" in metrics_data
    assert "baseline_first_fit_metrics" in metrics_data

    opt = metrics_data["optimizer_metrics"]
    base = metrics_data["baseline_first_fit_metrics"]

    # Verify metric properties
    assert opt["allocation_rate"] == 100.0
    assert opt["allocated_sessions"] == 2
    assert opt["unallocated_sessions"] == 0
    assert opt["room_conflict_count"] == 0
    assert opt["class_conflict_count"] == 0
    assert opt["seat_utilization"] > 0.0
    assert opt["runtime_ms"] >= 0.0

    # Verify baseline metrics
    assert base["allocation_rate"] == 100.0
    assert base["room_conflict_count"] == 0
    assert base["class_conflict_count"] == 0

