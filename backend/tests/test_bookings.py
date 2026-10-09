import pytest
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient


def test_reject_booking_when_capacity_insufficient_or_facility_missing(client: TestClient):
    proj = client.post("/api/v1/facilities", json={"name": "Projector B"}).json()
    room = client.post(
        "/api/v1/classrooms",
        json={"name": "Small Room", "capacity": 20, "room_type": "CLASSROOM"},
    ).json()

    # Query availability for 50 students -> must show not eligible due to capacity
    avail = client.get(
        "/api/v1/availability",
        params={
            "start_datetime": "2026-10-15T09:00:00",
            "end_datetime": "2026-10-15T10:00:00",
            "student_count": 50,
        },
    ).json()
    assert room["id"] not in [r["id"] for r in avail["eligible_rooms"]]
    eval_item = next(e for e in avail["evaluations"] if e["classroom"]["id"] == room["id"])
    assert eval_item["is_eligible"] is False
    assert any("Insufficient capacity" in reason for reason in eval_item["ineligibility_reasons"])

    # Query availability requiring Projector B which Small Room does not have
    avail_fac = client.get(
        "/api/v1/availability",
        params={
            "start_datetime": "2026-10-15T09:00:00",
            "end_datetime": "2026-10-15T10:00:00",
            "facility_ids": [proj["id"]],
        },
    ).json()
    assert room["id"] not in [r["id"] for r in avail_fac["eligible_rooms"]]


def test_reject_overlapping_bookings_for_same_room(client: TestClient):
    room = client.post(
        "/api/v1/classrooms",
        json={"name": "Conference Hall", "capacity": 50, "room_type": "CLASSROOM"},
    ).json()

    # Initial confirmed booking: 10:00 to 12:00
    b1 = client.post(
        "/api/v1/bookings",
        json={
            "room_id": room["id"],
            "title": "First Meeting",
            "start_datetime": "2026-10-15T10:00:00",
            "end_datetime": "2026-10-15T12:00:00",
            "status": "CONFIRMED",
        },
    )
    assert b1.status_code == 201

    # Overlapping booking 1: 11:00 to 13:00 (overlaps end)
    b2 = client.post(
        "/api/v1/bookings",
        json={
            "room_id": room["id"],
            "title": "Conflicting Meeting 1",
            "start_datetime": "2026-10-15T11:00:00",
            "end_datetime": "2026-10-15T13:00:00",
            "status": "CONFIRMED",
        },
    )
    assert b2.status_code == 409

    # Overlapping booking 2: 09:30 to 10:30 (overlaps start)
    b3 = client.post(
        "/api/v1/bookings",
        json={
            "room_id": room["id"],
            "title": "Conflicting Meeting 2",
            "start_datetime": "2026-10-15T09:30:00",
            "end_datetime": "2026-10-15T10:30:00",
            "status": "CONFIRMED",
        },
    )
    assert b3.status_code == 409

    # Overlapping booking 3: 10:15 to 11:45 (completely inside)
    b4 = client.post(
        "/api/v1/bookings",
        json={
            "room_id": room["id"],
            "title": "Conflicting Meeting 3",
            "start_datetime": "2026-10-15T10:15:00",
            "end_datetime": "2026-10-15T11:45:00",
            "status": "CONFIRMED",
        },
    )
    assert b4.status_code == 409


def test_allow_adjacent_non_overlapping_booking_intervals(client: TestClient):
    room = client.post(
        "/api/v1/classrooms",
        json={"name": "Adjacent Hall", "capacity": 50, "room_type": "CLASSROOM"},
    ).json()

    # First booking: 09:00 to 10:00
    b1 = client.post(
        "/api/v1/bookings",
        json={
            "room_id": room["id"],
            "title": "Morning Session 1",
            "start_datetime": "2026-10-16T09:00:00",
            "end_datetime": "2026-10-16T10:00:00",
            "status": "CONFIRMED",
        },
    )
    assert b1.status_code == 201

    # Second adjacent booking: exactly 10:00 to 11:00
    b2 = client.post(
        "/api/v1/bookings",
        json={
            "room_id": room["id"],
            "title": "Morning Session 2",
            "start_datetime": "2026-10-16T10:00:00",
            "end_datetime": "2026-10-16T11:00:00",
            "status": "CONFIRMED",
        },
    )
    assert b2.status_code == 201

    # Third adjacent booking: exactly 08:00 to 09:00 (preceding)
    b3 = client.post(
        "/api/v1/bookings",
        json={
            "room_id": room["id"],
            "title": "Early Session",
            "start_datetime": "2026-10-16T08:00:00",
            "end_datetime": "2026-10-16T09:00:00",
            "status": "CONFIRMED",
        },
    )
    assert b3.status_code == 201


def test_reject_booking_overlapping_maintenance(client: TestClient):
    room = client.post(
        "/api/v1/classrooms",
        json={"name": "Maintenance Hall", "capacity": 40, "room_type": "CLASSROOM"},
    ).json()

    # Create room unavailability (maintenance)
    unav = client.post(
        "/api/v1/room-unavailability",
        json={
            "room_id": room["id"],
            "start_datetime": "2026-10-17T13:00:00",
            "end_datetime": "2026-10-17T17:00:00",
            "reason": "Air conditioner repair",
        },
    )
    assert unav.status_code == 201

    # Attempt to book during maintenance
    booking = client.post(
        "/api/v1/bookings",
        json={
            "room_id": room["id"],
            "title": "Meeting During Maintenance",
            "start_datetime": "2026-10-17T14:00:00",
            "end_datetime": "2026-10-17T15:30:00",
            "status": "CONFIRMED",
        },
    )
    assert booking.status_code == 409


def test_cancelled_booking_frees_up_room(client: TestClient):
    room = client.post(
        "/api/v1/classrooms",
        json={"name": "Flexible Hall", "capacity": 40, "room_type": "CLASSROOM"},
    ).json()

    # Create booking
    b1 = client.post(
        "/api/v1/bookings",
        json={
            "room_id": room["id"],
            "title": "Event A",
            "start_datetime": "2026-10-18T10:00:00",
            "end_datetime": "2026-10-18T12:00:00",
            "status": "CONFIRMED",
        },
    ).json()

    # Cancel the booking
    cancel_resp = client.post(f"/api/v1/bookings/{b1['id']}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"

    # Now booking the exact same interval must succeed
    b2 = client.post(
        "/api/v1/bookings",
        json={
            "room_id": room["id"],
            "title": "Event B Replaces Event A",
            "start_datetime": "2026-10-18T10:00:00",
            "end_datetime": "2026-10-18T12:00:00",
            "status": "CONFIRMED",
        },
    )
    assert b2.status_code == 201


def test_concurrent_conflicting_booking_attempts(client: TestClient):
    room = client.post(
        "/api/v1/classrooms",
        json={"name": "High Contention Room", "capacity": 50, "room_type": "CLASSROOM"},
    ).json()

    def attempt_booking(title: str):
        return client.post(
            "/api/v1/bookings",
            json={
                "room_id": room["id"],
                "title": title,
                "start_datetime": "2026-10-19T14:00:00",
                "end_datetime": "2026-10-19T16:00:00",
                "status": "CONFIRMED",
            },
        )

    # Execute two simultaneous booking requests
    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(attempt_booking, "Attempt 1")
        f2 = executor.submit(attempt_booking, "Attempt 2")
        r1 = f1.result()
        r2 = f2.result()

    statuses = [r1.status_code, r2.status_code]
    # Exactly one must succeed (201) and one must be rejected (409)
    assert 201 in statuses
    assert 409 in statuses

