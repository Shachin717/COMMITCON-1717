from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Ensure both root and backend are in sys.path
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app.core.security import create_access_token
from app.models.enums import BookingStatus, RequesterType, RoomBlockReason, RoomStatus, RoomType, UserRole
from app.models import (
    Block,
    Booking,
    Department,
    Facility,
    Room,
    RoomBlock,
    RoomFacility,
    TimeSlot,
    TimetableEntry,
    User,
)
from app.services.allocation.config import AllocationWeights
from app.services.allocation.models import (
    Assignment,
    RequestItem,
    RoomCandidate,
)
from app.services.allocation.baseline import baseline_allocate
from app.services.allocation.optimizer import optimize_allocate
from app.services.allocation.metrics import compute_allocation_metrics
from app.services.allocation.reallocation import handle_room_unavailability
from scripts.generate_demo_requests import generate_demo_requests, generate_demo_rooms, run_demo_simulation


def test_demo_requests_simulation_numbers(capsys):
    """
    Test on 200 realistic demo requests asserting:
    1. Zero scheduling conflicts for baseline
    2. Zero scheduling conflicts for optimizer
    3. Optimized efficiency score >= baseline efficiency score
    4. Prints comparative numbers
    """
    requests = generate_demo_requests(count=200, seed=42)
    rooms = generate_demo_rooms()

    results = run_demo_simulation(requests=requests, rooms=rooms)

    bm = results["baseline"]["metrics"]
    om = results["optimized"]["metrics"]

    # Assertions required by prompt
    assert bm.conflict_count == 0, f"Baseline conflict count was {bm.conflict_count}, expected 0"
    assert om.conflict_count == 0, f"Optimizer conflict count was {om.conflict_count}, expected 0"
    assert om.efficiency_score >= bm.efficiency_score, (
        f"Optimized score ({om.efficiency_score}) should be >= Baseline score ({bm.efficiency_score})"
    )

    # Additional quality assertions
    assert om.facility_match_pct == 100.0, "Optimizer should strictly meet 100% of required facilities"
    assert om.preference_satisfaction_pct >= bm.preference_satisfaction_pct

    # Print summary output for inspection
    print("\n" + "=" * 70)
    print("DEMO SIMULATION TEST RESULTS (200 REQUESTS):")
    print(f"  • Baseline Efficiency Score  : {bm.efficiency_score:.2f}")
    print(f"  • Optimized Efficiency Score : {om.efficiency_score:.2f}")
    print(f"  • Score Delta               : +{om.efficiency_score - bm.efficiency_score:.2f}")
    print(f"  • Baseline Seat Utilization : {bm.seat_utilization_pct:.2f}%")
    print(f"  • Optimized Seat Utilization: {om.seat_utilization_pct:.2f}%")
    print(f"  • Baseline Facility Match   : {bm.facility_match_pct:.2f}%")
    print(f"  • Optimized Facility Match  : {om.facility_match_pct:.2f}%")
    print(f"  • Baseline Conflicts        : {bm.conflict_count}")
    print(f"  • Optimized Conflicts       : {om.conflict_count}")
    print("=" * 70)


def test_baseline_first_fit_allocator():
    """Verify baseline first-fit allocator processes in arrival order and ignores facilities."""
    room_small = RoomCandidate(
        id=1, name="R-1", block_id=1, block_name="B1", floor=1,
        room_type=RoomType.CLASSROOM, capacity=40, department_id=None,
        status=RoomStatus.ACTIVE, facilities=[]
    )
    room_large = RoomCandidate(
        id=2, name="R-2", block_id=1, block_name="B1", floor=1,
        room_type=RoomType.CLASSROOM, capacity=100, department_id=None,
        status=RoomStatus.ACTIVE, facilities=["projector"]
    )

    # Request requiring projector with strength 30 arrives
    req = RequestItem(
        id="R1", date=date(2026, 10, 15), slot_id=1, expected_strength=30,
        required_facilities=["projector"]
    )

    assignments = baseline_allocate([req], [room_small, room_large])
    assert len(assignments) == 1
    # Baseline picks the first free room whose capacity >= strength (id 1, capacity 40),
    # even though it lacks the required projector!
    assert assignments[0].allocated is True
    assert assignments[0].room.id == 1


def test_optimizer_hard_constraints():
    """Verify optimizer enforces capacity, facilities, room type, and active status as hard constraints."""
    target_date = date(2026, 10, 15)
    target_slot = 1

    room_small = RoomCandidate(
        id=1, name="R-1", block_id=1, block_name="B1", floor=1,
        room_type=RoomType.CLASSROOM, capacity=30, department_id=None,
        status=RoomStatus.ACTIVE, facilities=["projector"]
    )
    room_no_fac = RoomCandidate(
        id=2, name="R-2", block_id=1, block_name="B1", floor=1,
        room_type=RoomType.CLASSROOM, capacity=60, department_id=None,
        status=RoomStatus.ACTIVE, facilities=[]
    )
    room_lab = RoomCandidate(
        id=3, name="R-3", block_id=1, block_name="B1", floor=1,
        room_type=RoomType.LAB, capacity=60, department_id=None,
        status=RoomStatus.ACTIVE, facilities=["projector"]
    )
    room_perfect = RoomCandidate(
        id=4, name="R-4", block_id=1, block_name="B1", floor=1,
        room_type=RoomType.CLASSROOM, capacity=60, department_id=None,
        status=RoomStatus.ACTIVE, facilities=["projector"]
    )

    # Request requires capacity 50, CLASSROOM, projector
    req = RequestItem(
        id="REQ-A", date=target_date, slot_id=target_slot, expected_strength=50,
        room_type=RoomType.CLASSROOM, required_facilities=["projector"]
    )

    assignments = optimize_allocate([req], [room_small, room_no_fac, room_lab, room_perfect])
    assert len(assignments) == 1
    assert assignments[0].allocated is True
    assert assignments[0].room.id == 4  # Only room 4 satisfies all hard constraints!


def test_optimizer_soft_cost_minimizes_wastage():
    """Verify optimizer chooses tighter capacity room over overly large room."""
    target_date = date(2026, 10, 15)
    target_slot = 1

    room_huge = RoomCandidate(
        id=1, name="R-Huge", block_id=1, block_name="B1", floor=1,
        room_type=RoomType.CLASSROOM, capacity=120, department_id=None,
        status=RoomStatus.ACTIVE, facilities=["projector"]
    )
    room_snug = RoomCandidate(
        id=2, name="R-Snug", block_id=1, block_name="B1", floor=1,
        room_type=RoomType.CLASSROOM, capacity=50, department_id=None,
        status=RoomStatus.ACTIVE, facilities=["projector"]
    )

    req = RequestItem(
        id="REQ-1", date=target_date, slot_id=target_slot, expected_strength=45,
        room_type=RoomType.CLASSROOM, required_facilities=["projector"]
    )

    assignments = optimize_allocate([req], [room_huge, room_snug])
    assert len(assignments) == 1
    assert assignments[0].room.id == 2  # Snug room chosen to minimize empty seats wastage!


def test_reallocation_service(db_session: Session):
    """Verify reallocation when a room enters MAINTENANCE."""
    # Setup test departments and blocks
    block_a = Block(name="Block Test A", description="Test")
    block_b = Block(name="Block Test B", description="Test")
    dept = Department(name="Computer Science", code="CS_TEST", hod_approval_required=False)
    db_session.add_all([block_a, block_b, dept])
    db_session.flush()

    # Create slot
    from datetime import time
    slot = TimeSlot(label="09:00 AM - 10:00 AM", start_time=time(9, 0), end_time=time(10, 0), order=1)
    db_session.add(slot)
    db_session.flush()

    # Room 1: Affected room
    room_orig = Room(
        name="Orig-101", block_id=block_a.id, floor=1, room_type=RoomType.CLASSROOM,
        capacity=50, status=RoomStatus.ACTIVE
    )
    # Room 2: Replacement in same block
    room_rep = Room(
        name="Rep-102", block_id=block_a.id, floor=1, room_type=RoomType.CLASSROOM,
        capacity=55, status=RoomStatus.ACTIVE
    )
    db_session.add_all([room_orig, room_rep])
    db_session.flush()

    # Create active booking in room_orig
    booking_date = date.today() + timedelta(days=2)
    booking = Booking(
        reference="RELOC-001",
        room_id=room_orig.id,
        date=booking_date,
        slot_id=slot.id,
        purpose="Database Lecture",
        expected_strength=40,
        required_facilities=[],
        status=BookingStatus.APPROVED,
        requester_type=RequesterType.STUDENT,
        roll_no="CS101",
        name="Student Test",
        department_id=dept.id,
        phone="9876543210",
        email="test_reloc@college.edu",
    )
    db_session.add(booking)
    db_session.commit()

    # Mark room MAINTENANCE and trigger reallocation
    room_orig.status = RoomStatus.MAINTENANCE
    db_session.commit()

    response = handle_room_unavailability(
        db=db_session,
        room_id=room_orig.id,
        reason=RoomBlockReason.MAINTENANCE,
        start_date=booking_date,
        send_notifications=False,
    )

    assert response.affected_count == 1
    assert response.relocated_count == 1
    assert response.relocated_bookings[0].replacement_room_id == room_rep.id

    # Verify booking status changed to RELOCATED
    db_session.refresh(booking)
    assert booking.status == BookingStatus.RELOCATED
    assert "Rep-102" in booking.decision_note


def test_allocation_api_endpoints(client: TestClient, seed_users, db_session: Session):
    """Test API endpoints: /api/allocation/simulate, /api/allocation/apply, /api/allocation/metrics/history."""
    admin_user = seed_users["admin"]
    token = create_access_token(
        subject=admin_user.id,
        extra_claims={"email": admin_user.email, "role": admin_user.role.value},
    )
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Setup minimal seed room in db
    block = Block(name="API Block", description="API Test Block")
    dept = Department(name="IT Dept", code="IT_API", hod_approval_required=False)
    db_session.add_all([block, dept])
    db_session.flush()

    from datetime import time
    slot = TimeSlot(label="10:00 AM - 11:00 AM", start_time=time(10, 0), end_time=time(11, 0), order=2)
    db_session.add(slot)
    db_session.flush()

    room = Room(
        name="API-201", block_id=block.id, floor=2, room_type=RoomType.CLASSROOM,
        capacity=60, status=RoomStatus.ACTIVE
    )
    db_session.add(room)
    db_session.commit()

    # 2. Test /api/allocation/simulate with custom requests
    target_date = str(date.today() + timedelta(days=3))
    sim_payload = {
        "start_date": target_date,
        "end_date": target_date,
        "use_existing_bookings": False,
        "requests": [
            {
                "id": "REQ-API-1",
                "date": target_date,
                "slot_id": slot.id,
                "expected_strength": 40,
                "room_type": "CLASSROOM",
                "required_facilities": [],
                "department_id": dept.id,
                "roll_no": "20240101",
                "name": "API Student",
                "email": "student@college.edu",
            }
        ]
    }

    res_sim = client.post("/api/allocation/simulate", json=sim_payload, headers=headers)
    assert res_sim.status_code == 200, res_sim.text
    data_sim = res_sim.json()
    assert data_sim["total_requests"] == 1
    assert "baseline" in data_sim
    assert "optimized" in data_sim
    assert "comparison" in data_sim
    assert data_sim["optimized"]["metrics"]["conflict_count"] == 0

    # 3. Test /api/allocation/apply
    res_apply = client.post("/api/allocation/apply", json=sim_payload, headers=headers)
    assert res_apply.status_code == 200, res_apply.text
    data_apply = res_apply.json()
    assert data_apply["status"] == "SUCCESS"
    assert data_apply["applied_count"] == 1

    # 4. Test /api/allocation/metrics/history
    res_hist = client.get("/api/allocation/metrics/history", headers=headers)
    assert res_hist.status_code == 200, res_hist.text
    data_hist = res_hist.json()
    assert data_hist["total"] >= 2  # simulate + apply recorded
    assert len(data_hist["items"]) >= 2

    # 5. Authorization: unauthenticated request rejected
    res_unauth = client.get("/api/allocation/metrics/history")
    assert res_unauth.status_code == 401


def test_demo_requests_and_insights_features(client: TestClient, seed_users, db_session: Session):
    """Test demo generation, heatmap matrix, wastage distribution, and preview reallocation."""
    admin_user = seed_users["admin"]
    coord_user = seed_users["coordinator"]
    admin_token = create_access_token(
        subject=admin_user.id,
        extra_claims={"email": admin_user.email, "role": admin_user.role.value},
    )
    coord_token = create_access_token(
        subject=coord_user.id,
        extra_claims={"email": coord_user.email, "role": coord_user.role.value},
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    coord_headers = {"Authorization": f"Bearer {coord_token}"}

    # 1. Setup seed room in maintenance
    block = Block(name="Science Block", description="Science Wing")
    dept = Department(name="Physics", code="PHY", hod_approval_required=False)
    db_session.add_all([block, dept])
    db_session.flush()

    from datetime import time
    slot = TimeSlot(label="09:00 AM - 10:00 AM", start_time=time(9, 0), end_time=time(10, 0), order=1)
    db_session.add(slot)
    db_session.flush()

    room_maint = Room(
        name="SCI-101", block_id=block.id, floor=1, room_type=RoomType.CLASSROOM,
        capacity=60, status=RoomStatus.MAINTENANCE, maintenance_note="HVAC repair"
    )
    room_alt = Room(
        name="SCI-102", block_id=block.id, floor=1, room_type=RoomType.CLASSROOM,
        capacity=70, status=RoomStatus.ACTIVE
    )
    db_session.add_all([room_maint, room_alt])
    db_session.commit()

    # 2. Test /api/allocation/demo-requests
    res_demo = client.get("/api/allocation/demo-requests?count=5", headers=coord_headers)
    assert res_demo.status_code == 200, res_demo.text
    demos = res_demo.json()
    assert len(demos) == 5
    assert "expected_strength" in demos[0]
    assert "slot_id" in demos[0]

    # 3. Test /api/allocation/maintenance-rooms
    res_maint = client.get("/api/allocation/maintenance-rooms", headers=coord_headers)
    assert res_maint.status_code == 200, res_maint.text
    maint_data = res_maint.json()
    assert maint_data["total"] >= 1
    assert any(r["name"] == "SCI-101" for r in maint_data["rooms"])

    # 4. Test /api/allocation/simulate with generate_demo=True
    sim_payload = {
        "start_date": str(date.today()),
        "end_date": str(date.today() + timedelta(days=2)),
        "generate_demo": True,
        "demo_count": 8,
    }
    res_sim = client.post("/api/allocation/simulate", json=sim_payload, headers=coord_headers)
    assert res_sim.status_code == 200, res_sim.text
    sim_data = res_sim.json()
    assert sim_data["total_requests"] == 8
    assert "wastage_distribution" in sim_data
    assert "heatmap_matrix" in sim_data
    assert "maintenance_rooms" in sim_data
    assert len(sim_data["wastage_distribution"]) == 5  # 5 standard buckets
    assert len(sim_data["heatmap_matrix"]) >= 2

    # 5. Test reallocation preview on maintenance room
    # Add a booking on room_maint
    bk = Booking(
        reference="RELOC-TEST-1",
        room_id=room_maint.id,
        date=date.today() + timedelta(days=1),
        slot_id=slot.id,
        purpose="Physics Lecture",
        expected_strength=40,
        status=BookingStatus.APPROVED,
        requester_type=RequesterType.STUDENT,
        roll_no="2026PHY01",
        name="Physics Student",
        department_id=dept.id,
        phone="9876543210",
        email="student.phy@college.edu",
    )
    db_session.add(bk)
    db_session.commit()

    realloc_payload = {
        "room_id": room_maint.id,
        "reason": "MAINTENANCE",
        "start_date": str(date.today()),
        "end_date": str(date.today() + timedelta(days=2)),
        "send_notifications": False,
        "preview_only": True,
    }
    res_realloc_prev = client.post("/api/allocation/reallocate", json=realloc_payload, headers=admin_headers)
    assert res_realloc_prev.status_code == 200, res_realloc_prev.text
    realloc_data = res_realloc_prev.json()
    assert realloc_data["affected_count"] >= 1
    assert realloc_data["relocated_count"] >= 1
    assert realloc_data["relocated_bookings"][0]["replacement_room_name"] == "SCI-102"
    # Verify booking status remains APPROVED in preview mode
    db_session.refresh(bk)
    assert bk.status == BookingStatus.APPROVED

