#!/usr/bin/env python3
"""
Generate 200 realistic random room allocation requests and run baseline vs optimized simulation.
Can be executed as a standalone script or imported by pytest.
"""
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import random
import sys
from typing import Dict, List, Optional, Tuple, Any

# Ensure backend is on sys.path
root_dir = Path(__file__).resolve().parents[1]
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.models.enums import RoomStatus, RoomType
from app.services.allocation.config import AllocationWeights
from app.services.allocation.models import (
    Assignment,
    RequestItem,
    RoomCandidate,
)
from app.services.allocation.baseline import baseline_allocate
from app.services.allocation.optimizer import optimize_allocate
from app.services.allocation.metrics import compute_allocation_metrics


def generate_demo_rooms() -> List[RoomCandidate]:
    """Returns a realistic set of 28 rooms across 4 physical blocks in a college."""
    rooms_data = [
        # Block 1 - Main Academic (Classrooms & Seminar Halls)
        (1, "A-101", 1, "Block A - Main Academic", 1, RoomType.CLASSROOM, 40, 1, ["projector"]),
        (2, "A-102", 1, "Block A - Main Academic", 1, RoomType.CLASSROOM, 60, 1, ["projector", "ac"]),
        (3, "A-201", 1, "Block A - Main Academic", 2, RoomType.CLASSROOM, 60, 2, ["projector"]),
        (4, "A-202", 1, "Block A - Main Academic", 2, RoomType.CLASSROOM, 80, 2, ["projector", "smart_board", "ac"]),
        (5, "A-301", 1, "Block A - Main Academic", 3, RoomType.CLASSROOM, 60, None, ["projector"]),
        (6, "A-302", 1, "Block A - Main Academic", 3, RoomType.CLASSROOM, 100, None, ["projector", "sound_system"]),
        (7, "A-AUD", 1, "Block A - Main Academic", 1, RoomType.SEMINAR_HALL, 150, None, ["projector", "ac", "sound_system", "mic"]),

        # Block 2 - Tech & Computing (CS Labs & Lecture Rooms)
        (8, "B-101", 2, "Block B - Tech & Computing", 1, RoomType.LAB, 40, 1, ["pcs", "projector", "ac"]),
        (9, "B-102", 2, "Block B - Tech & Computing", 1, RoomType.LAB, 60, 1, ["pcs", "projector", "ac"]),
        (10, "B-201", 2, "Block B - Tech & Computing", 2, RoomType.LAB, 50, 3, ["pcs", "projector", "ac"]),
        (11, "B-202", 2, "Block B - Tech & Computing", 2, RoomType.CLASSROOM, 60, 1, ["projector", "smart_board"]),
        (12, "B-301", 2, "Block B - Tech & Computing", 3, RoomType.CLASSROOM, 70, 3, ["projector", "ac"]),
        (13, "B-302", 2, "Block B - Tech & Computing", 3, RoomType.CLASSROOM, 90, None, ["projector"]),
        (14, "B-SEMINAR", 2, "Block B - Tech & Computing", 2, RoomType.SEMINAR_HALL, 120, 1, ["projector", "ac", "mic", "sound_system"]),

        # Block 3 - Core Engineering (Mechanical & Civil)
        (15, "C-101", 3, "Block C - Core Engineering", 1, RoomType.CLASSROOM, 60, 4, ["projector"]),
        (16, "C-102", 3, "Block C - Core Engineering", 1, RoomType.LAB, 50, 4, ["lab_equipment", "projector"]),
        (17, "C-201", 3, "Block C - Core Engineering", 2, RoomType.CLASSROOM, 75, 4, ["projector", "smart_board"]),
        (18, "C-202", 3, "Block C - Core Engineering", 2, RoomType.CLASSROOM, 60, 5, ["projector"]),
        (19, "C-301", 3, "Block C - Core Engineering", 3, RoomType.LAB, 45, 5, ["lab_equipment"]),
        (20, "C-302", 3, "Block C - Core Engineering", 3, RoomType.CLASSROOM, 80, None, ["projector"]),
        (21, "C-EXAM", 3, "Block C - Core Engineering", 1, RoomType.EXAM_HALL, 180, None, ["ac", "sound_system"]),

        # Block 4 - PG & Innovation (Management & Advanced Studies)
        (22, "D-101", 4, "Block D - PG & Innovation", 1, RoomType.CLASSROOM, 50, 6, ["projector", "ac"]),
        (23, "D-102", 4, "Block D - PG & Innovation", 1, RoomType.CLASSROOM, 60, 6, ["projector", "ac", "smart_board"]),
        (24, "D-201", 4, "Block D - PG & Innovation", 2, RoomType.CLASSROOM, 70, 6, ["projector", "ac"]),
        (25, "D-202", 4, "Block D - PG & Innovation", 2, RoomType.LAB, 40, 6, ["pcs", "ac"]),
        (26, "D-301", 4, "Block D - PG & Innovation", 3, RoomType.CLASSROOM, 55, None, ["projector"]),
        (27, "D-302", 4, "Block D - PG & Innovation", 3, RoomType.CLASSROOM, 85, None, ["projector", "ac"]),
        (28, "D-AUD", 4, "Block D - PG & Innovation", 1, RoomType.SEMINAR_HALL, 200, None, ["projector", "ac", "sound_system", "mic", "smart_board"]),
    ]

    rooms: List[RoomCandidate] = []
    for r in rooms_data:
        rooms.append(
            RoomCandidate(
                id=r[0],
                name=r[1],
                block_id=r[2],
                block_name=r[3],
                floor=r[4],
                room_type=r[5],
                capacity=r[6],
                department_id=r[7],
                status=RoomStatus.ACTIVE,
                facilities=r[8],
            )
        )
    return rooms


def generate_demo_requests(count: int = 200, seed: int = 42) -> List[RequestItem]:
    """
    Generates realistic, deterministic random room allocation requests.
    Includes diverse student class strengths, facility combinations,
    department associations, and arrival timestamps.
    """
    random.seed(seed)

    base_date = date(2026, 10, 12)  # Monday
    date_pool = [base_date + timedelta(days=i) for i in range(5)]  # Mon - Fri
    slots_pool = list(range(1, 9))  # 8 daily time slots

    dept_block_map = {
        1: (1, [1, 2]),  # CSE: Block 2 (Tech), floor 1-2
        2: (2, [1, 2]),  # ECE: Block 1 (Main), floor 2
        3: (2, [2, 3]),  # ISE: Block 2 (Tech), floor 2-3
        4: (3, [1, 2]),  # MECH: Block 3 (Core), floor 1-2
        5: (3, [2, 3]),  # CIVIL: Block 3 (Core), floor 2-3
        6: (4, [1, 2]),  # MBA: Block 4 (PG), floor 1-2
    }

    facility_profiles = [
        [],
        ["projector"],
        ["projector", "ac"],
        ["projector", "smart_board"],
        ["pcs", "projector"],
        ["projector", "sound_system"],
        ["ac", "mic", "sound_system"],
    ]

    first_names = [
        "Aarav", "Ananya", "Rohan", "Sneha", "Vikram", "Pooja", "Aditya", "Divya",
        "Karthik", "Meera", "Arjun", "Neha", "Sanjay", "Kavya", "Rahul", "Priya",
        "Nikhil", "Deepa", "Varun", "Isha", "Manish", "Anjali", "Siddharth", "Ritu"
    ]
    last_names = [
        "Sharma", "Patel", "Reddy", "Iyer", "Nair", "Verma", "Kulkarni", "Deshmukh",
        "Rao", "Menon", "Joshi", "Gupta", "Mehta", "Bhat", "Chopra", "Das"
    ]

    purposes = [
        "Algorithms & Data Structures Lecture",
        "Machine Learning Laboratory Session",
        "Signals & Systems Tutorial",
        "Fluid Dynamics Problem Solving",
        "Thermodynamics Workshop",
        "Embedded Systems Practicum",
        "Marketing Analytics Case Study",
        "Software Engineering Project Review",
        "Database Management Systems Lab",
        "Web Technologies Interactive Lecture",
        "Guest Lecture on Quantum Computing",
        "Robotics Club Technical Hands-on",
        "Departmental Faculty Colloquium",
        "Pre-placement Aptitude Training",
        "Student Council Seminar",
    ]

    requests: List[RequestItem] = []
    base_timestamp = datetime(2026, 10, 8, 8, 0, 0)

    # Some groups book 2 consecutive slots to test split penalty
    current_req_idx = 1
    while len(requests) < count:
        target_date = random.choice(date_pool)
        dept_id = random.randint(1, 6)
        preferred_block_id, floors = dept_block_map[dept_id]
        preferred_floor = random.choice(floors)

        # 75% Classroom, 18% Lab, 7% Seminar
        type_roll = random.random()
        if type_roll < 0.75:
            room_type = RoomType.CLASSROOM
            expected_strength = random.choice([30, 35, 45, 50, 55, 60, 70, 75])
            facs = random.choice(facility_profiles[:4])
        elif type_roll < 0.93:
            room_type = RoomType.LAB
            expected_strength = random.choice([30, 35, 40, 45, 50])
            facs = ["pcs", "projector"] if dept_id in (1, 3, 6) else ["lab_equipment"]
        else:
            room_type = RoomType.SEMINAR_HALL
            expected_strength = random.choice([80, 100, 120, 140])
            facs = ["projector", "sound_system", "mic"]

        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        roll_no = f"2023{dept_id:02d}{random.randint(100, 999)}"
        email = f"{roll_no.lower()}@college.edu"
        purpose = random.choice(purposes)

        # 25% chance of booking a 2-slot sequence for the same group
        has_two_slots = (random.random() < 0.25) and (len(requests) < count - 1)
        slot_1 = random.randint(1, 7 if has_two_slots else 8)

        # Arrival timestamp simulates early vs late bookings
        arrival_minutes = random.randint(0, 7200)  # over 5 days
        created_at_1 = base_timestamp + timedelta(minutes=arrival_minutes)

        req1 = RequestItem(
            id=f"DEMO_{current_req_idx:03d}",
            date=target_date,
            slot_id=slot_1,
            expected_strength=expected_strength,
            room_type=room_type,
            required_facilities=facs,
            department_id=dept_id,
            preferred_block_id=preferred_block_id,
            preferred_floor=preferred_floor,
            created_at=created_at_1,
            requester_id=roll_no,
            name=name,
            email=email,
            purpose=purpose,
        )
        requests.append(req1)
        current_req_idx += 1

        if has_two_slots:
            req2 = RequestItem(
                id=f"DEMO_{current_req_idx:03d}",
                date=target_date,
                slot_id=slot_1 + 1,
                expected_strength=expected_strength,
                room_type=room_type,
                required_facilities=facs,
                department_id=dept_id,
                preferred_block_id=preferred_block_id,
                preferred_floor=preferred_floor,
                created_at=created_at_1 + timedelta(minutes=1),
                requester_id=roll_no,
                name=name,
                email=email,
                purpose=f"{purpose} (Part 2)",
            )
            requests.append(req2)
            current_req_idx += 1

    return requests[:count]


def run_demo_simulation(
    requests: Optional[List[RequestItem]] = None,
    rooms: Optional[List[RoomCandidate]] = None,
    weights: Optional[AllocationWeights] = None,
) -> Dict[str, Any]:
    """Runs baseline and optimizer on requests and returns comparison metrics."""
    if rooms is None:
        rooms = generate_demo_rooms()
    if requests is None:
        requests = generate_demo_requests(200)
    if weights is None:
        weights = AllocationWeights()

    # Run Baseline
    baseline_assignments = baseline_allocate(requests, rooms)
    baseline_metrics = compute_allocation_metrics(baseline_assignments)

    # Run Optimizer
    optimized_assignments = optimize_allocate(requests, rooms, weights=weights)
    optimized_metrics = compute_allocation_metrics(optimized_assignments)

    return {
        "total_requests": len(requests),
        "total_rooms": len(rooms),
        "baseline": {
            "metrics": baseline_metrics,
            "assignments": baseline_assignments,
        },
        "optimized": {
            "metrics": optimized_metrics,
            "assignments": optimized_assignments,
        },
    }


def print_comparison_table(results: Dict[str, Any]) -> None:
    """Pretty prints the simulation comparison table."""
    bm = results["baseline"]["metrics"]
    om = results["optimized"]["metrics"]

    print("\n" + "=" * 80)
    print(" 🏫 SMART CLASSROOM ALLOCATION ENGINE — DEMO SIMULATION (200 REQUESTS)")
    print("=" * 80)
    print(f"{'Metric':<34} | {'Baseline (First-Fit)':<20} | {'Optimized (scipy)':<20}")
    print("-" * 80)
    print(f"{'Total Requests':<34} | {bm.total_requests:<20} | {om.total_requests:<20}")
    print(f"{'Allocated Count':<34} | {bm.allocated_count:<20} | {om.allocated_count:<20}")
    print(f"{'Unallocated Count':<34} | {bm.unallocated_count:<20} | {om.unallocated_count:<20}")
    print(f"{'Allocation Rate %':<34} | {bm.allocation_rate_pct:>18.2f}% | {om.allocation_rate_pct:>18.2f}%")
    print(f"{'Seat Utilization %':<34} | {bm.seat_utilization_pct:>18.2f}% | {om.seat_utilization_pct:>18.2f}%")
    print(f"{'Average Space Wastage %':<34} | {bm.average_wastage_pct:>18.2f}% | {om.average_wastage_pct:>18.2f}%")
    print(f"{'Facility Match %':<34} | {bm.facility_match_pct:>18.2f}% | {om.facility_match_pct:>18.2f}%")
    print(f"{'Preference Satisfaction %':<34} | {bm.preference_satisfaction_pct:>18.2f}% | {om.preference_satisfaction_pct:>18.2f}%")
    print(f"{'Scheduling Conflicts (Must be 0)':<34} | {bm.conflict_count:<20} | {om.conflict_count:<20}")
    print(f"{'Block Switches Count':<34} | {bm.block_switch_count:<20} | {om.block_switch_count:<20}")
    print("-" * 80)
    print(f"{'⭐ Combined Efficiency Score (0-100)':<34} | {bm.efficiency_score:>18.2f}  | {om.efficiency_score:>18.2f} ")
    print("=" * 80)

    score_diff = om.efficiency_score - bm.efficiency_score
    util_diff = om.seat_utilization_pct - bm.seat_utilization_pct
    wastage_diff = bm.average_wastage_pct - om.average_wastage_pct
    fac_diff = om.facility_match_pct - bm.facility_match_pct
    pref_diff = om.preference_satisfaction_pct - bm.preference_satisfaction_pct

    print(f"📊 SUMMARY OF IMPROVEMENTS:")
    print(f"   • Efficiency Score Improvement : +{score_diff:.2f} pts")
    print(f"   • Seat Utilization Gain        : +{util_diff:.2f}%")
    print(f"   • Capacity Wastage Reduced by  : -{wastage_diff:.2f}%")
    print(f"   • Facility Match Gain          : +{fac_diff:.2f}%")
    print(f"   • Preference Satisfaction Gain : +{pref_diff:.2f}%")
    print("=" * 80 + "\n")


def main():
    print("🚀 Generating 200 realistic random requests...")
    requests = generate_demo_requests(200)
    rooms = generate_demo_rooms()

    # Save demo requests to JSON file for reference
    json_path = root_dir / "scripts" / "demo_requests.json"
    serializable_requests = [
        {
            "id": r.id,
            "date": str(r.date),
            "slot_id": r.slot_id,
            "expected_strength": r.expected_strength,
            "room_type": r.room_type.value if r.room_type else "CLASSROOM",
            "required_facilities": r.required_facilities,
            "department_id": r.department_id,
            "preferred_block_id": r.preferred_block_id,
            "preferred_floor": r.preferred_floor,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "requester_id": r.requester_id,
            "name": r.name,
            "email": r.email,
            "purpose": r.purpose,
        }
        for r in requests
    ]
    with open(json_path, "w") as f:
        json.dump(serializable_requests, f, indent=2)
    print(f"💾 Saved {len(requests)} demo requests to {json_path}")

    print("⚙️ Running baseline first-fit vs scipy linear sum assignment optimizer...")
    results = run_demo_simulation(requests=requests, rooms=rooms)
    print_comparison_table(results)


if __name__ == "__main__":
    main()

