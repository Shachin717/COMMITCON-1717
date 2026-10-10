from datetime import date, datetime, timedelta
import random
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.block import Block
from app.models.department import Department
from app.models.enums import RoomStatus, RoomType
from app.models.room import Room
from app.models.time_slot import TimeSlot
from app.schemas.allocation import AllocationRequestItem


def generate_demo_allocation_requests(
    db: Session,
    count: int = 25,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    seed: int = 42,
) -> List[AllocationRequestItem]:
    """
    Generates realistic, varied academic room booking requests tailored to
    the actual departments, blocks, and time slots in the database.
    """
    rng = random.Random(seed)

    if start_date is None:
        start_date = date.today()
    if end_date is None:
        end_date = start_date + timedelta(days=2)
    if end_date < start_date:
        end_date = start_date

    # Load DB entities
    time_slots = db.query(TimeSlot).order_by(TimeSlot.order).all()
    slot_ids = [ts.id for ts in time_slots] if time_slots else list(range(1, 9))

    departments = db.query(Department).all()
    dept_ids = [d.id for d in departments] if departments else [1]

    blocks = db.query(Block).all()
    block_ids = [b.id for b in blocks] if blocks else [1]

    # Calculate days in window
    day_diff = (end_date - start_date).days
    date_pool = [start_date + timedelta(days=i) for i in range(day_diff + 1)]

    purposes = [
        "Advanced Data Structures Lecture",
        "Computer Networks Lab Practicum",
        "Signals & Systems Interactive Problem Solving",
        "Fluid Dynamics Workshop",
        "Thermodynamics Analysis Seminar",
        "Embedded Systems Microcontroller Lab",
        "Marketing Analytics Case Discussion",
        "Software Engineering Capstone Review",
        "Database Architecture & Indexing Lab",
        "Full-Stack Web Development Practicum",
        "Guest Keynote on Artificial Intelligence",
        "Robotics Club Hardware Hack Session",
        "Department Academic Colloquium",
        "Campus Placement Technical Training",
        "Student Leadership Forum",
        "Discrete Mathematics Tutorial",
        "VLSI Design & Verification Lab",
        "Operating Systems Kernel Seminar",
    ]

    facility_pools = [
        [],
        ["projector"],
        ["projector", "ac"],
        ["projector", "smart_board"],
        ["pcs", "projector"],
        ["projector", "ac", "sound_system"],
        ["ac", "mic", "sound_system"],
        ["lab_equipment"],
    ]

    first_names = [
        "Aarav", "Ananya", "Rohan", "Sneha", "Vikram", "Pooja", "Aditya", "Divya",
        "Karthik", "Meera", "Arjun", "Neha", "Sanjay", "Kavya", "Rahul", "Priya",
        "Nikhil", "Deepa", "Varun", "Isha", "Manish", "Anjali", "Siddharth", "Ritu",
        "Tanya", "Akash", "Swati", "Gaurav", "Harini", "Chetan"
    ]
    last_names = [
        "Sharma", "Patel", "Reddy", "Iyer", "Nair", "Verma", "Kulkarni", "Deshmukh",
        "Rao", "Menon", "Joshi", "Gupta", "Mehta", "Bhat", "Chopra", "Das"
    ]

    items: List[AllocationRequestItem] = []

    for i in range(count):
        r_date = rng.choice(date_pool)
        r_slot = rng.choice(slot_ids)
        r_dept = rng.choice(dept_ids)
        r_block = rng.choice(block_ids) if block_ids else None
        r_floor = rng.randint(1, 4)

        # Decide room type & strength profile
        type_roll = rng.random()
        if type_roll < 0.65:
            room_type = RoomType.CLASSROOM
            expected_strength = rng.choice([25, 30, 35, 45, 50, 60, 70])
            facs = rng.choice(facility_pools[:4])
        elif type_roll < 0.88:
            room_type = RoomType.LAB
            expected_strength = rng.choice([25, 30, 35, 40, 50])
            facs = ["pcs", "projector"] if rng.random() > 0.5 else ["lab_equipment"]
        else:
            room_type = RoomType.SEMINAR_HALL
            expected_strength = rng.choice([75, 90, 110, 130])
            facs = ["projector", "ac", "sound_system", "mic"]

        name = f"{rng.choice(first_names)} {rng.choice(last_names)}"
        roll_num = f"2026{r_dept:02d}{rng.randint(100, 999)}"
        email = f"{roll_num.lower()}@college.edu"
        purpose = rng.choice(purposes)

        items.append(
            AllocationRequestItem(
                id=f"demo_{i + 1}",
                date=r_date,
                slot_id=r_slot,
                expected_strength=expected_strength,
                room_type=room_type,
                required_facilities=facs,
                department_id=r_dept,
                preferred_block_id=r_block,
                preferred_floor=r_floor,
                roll_no=roll_num,
                name=name,
                email=email,
                class_name=f"Batch-{chr(65 + (i % 6))}",
                phone=f"98765{rng.randint(10000, 99999)}",
                purpose=purpose,
                created_at=datetime.now(),
            )
        )

    return items

