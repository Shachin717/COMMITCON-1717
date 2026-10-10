#!/usr/bin/env python3
"""Database seed script for Smart Classroom Allocation System."""
import os
import sys
import random
from datetime import time
from pathlib import Path

# Add backend directory to sys.path so app modules can be loaded
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select, delete, text
from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.models.enums import UserRole, RoomType, RoomStatus, RoomBlockReason, BookingStatus, RequesterType
from app.models import (
    Base,
    User,
    Department,
    Block,
    BlockCoordinator,
    Facility,
    RoomFacility,
    Room,
    TimeSlot,
    TimetableEntry,
    RoomBlock,
    Booking,
    OtpCode,
    AuditLog,
)


def seed_database():
    print("🌱 Starting database seeding...")
    db = SessionLocal()

    try:
        # 1. Clear existing seedable data in proper dependency order
        print("🧹 Cleaning existing data...")
        db.query(TimetableEntry).delete()
        db.query(Booking).delete()
        db.query(RoomBlock).delete()
        db.query(RoomFacility).delete()
        db.query(BlockCoordinator).delete()
        db.query(Room).delete()
        db.query(Facility).delete()
        db.query(TimeSlot).delete()
        db.query(User).delete()
        db.query(Block).delete()
        db.query(Department).delete()
        db.query(OtpCode).delete()
        db.query(AuditLog).delete()
        db.commit()

        # 2. Seed 6 Departments
        print("🏢 Seeding 6 Departments...")
        departments_data = [
            {"name": "Computer Science & Engineering", "code": "CSE", "hod_approval_required": True},
            {"name": "Electronics & Communication Engineering", "code": "ECE", "hod_approval_required": True},
            {"name": "Information Science & Engineering", "code": "ISE", "hod_approval_required": True},
            {"name": "Mechanical Engineering", "code": "MECH", "hod_approval_required": True},
            {"name": "Civil Engineering", "code": "CIVIL", "hod_approval_required": False},
            {"name": "Master of Business Administration", "code": "MBA", "hod_approval_required": False},
        ]
        dept_objs = {}
        for d in departments_data:
            dept = Department(**d)
            db.add(dept)
            dept_objs[d["code"]] = dept
        db.flush()

        # 3. Seed 4 Blocks
        print("🏛️  Seeding 4 Blocks...")
        blocks_data = [
            {"name": "Block A - Main Academic", "description": "Primary academic building with multimedia lecture halls"},
            {"name": "Block B - Tech & Computing", "description": "High-tech laboratories and computational research centres"},
            {"name": "Block C - Core Engineering", "description": "Mechanical and Civil engineering workshops and drawing halls"},
            {"name": "Block D - PG & Innovation", "description": "Postgraduate suites, seminar halls, and smart collaborative spaces"},
        ]
        block_objs = []
        for b in blocks_data:
            blk = Block(**b)
            db.add(blk)
            block_objs.append(blk)
        db.flush()

        # 4. Seed 8 Time Slots
        print("⏰ Seeding 8 Time Slots...")
        slots_data = [
            {"order": 1, "label": "08:30 AM - 09:30 AM", "start_time": time(8, 30), "end_time": time(9, 30)},
            {"order": 2, "label": "09:30 AM - 10:30 AM", "start_time": time(9, 30), "end_time": time(10, 30)},
            {"order": 3, "label": "10:45 AM - 11:45 AM", "start_time": time(10, 45), "end_time": time(11, 45)},
            {"order": 4, "label": "11:45 AM - 12:45 PM", "start_time": time(11, 45), "end_time": time(12, 45)},
            {"order": 5, "label": "01:30 PM - 02:30 PM", "start_time": time(13, 30), "end_time": time(14, 30)},
            {"order": 6, "label": "02:30 PM - 03:30 PM", "start_time": time(14, 30), "end_time": time(15, 30)},
            {"order": 7, "label": "03:45 PM - 04:45 PM", "start_time": time(15, 45), "end_time": time(16, 45)},
            {"order": 8, "label": "04:45 PM - 05:45 PM", "start_time": time(16, 45), "end_time": time(17, 45)},
        ]
        slot_objs = []
        for s in slots_data:
            ts = TimeSlot(**s)
            db.add(ts)
            slot_objs.append(ts)
        db.flush()

        # 5. Seed ~15 Facilities
        print("🛠️  Seeding 15 Facilities...")
        facility_names = [
            "Projector",
            "Air Conditioner",
            "Smart Interactive Board",
            "High-End Workstations",
            "Microphone & Audio System",
            "High-Speed Gigabit WiFi",
            "Document Camera",
            "Video Conferencing Rig",
            "Magnetic Whiteboard & Podium",
            "Specialized Lab Equipment",
            "UPS Power Backup",
            "Wheelchair Accessible Ramp",
            "Surround Sound Acoustic System",
            "Automated Lecture Recording Unit",
            "Tiered Step Seating",
        ]
        facility_objs = []
        for fname in facility_names:
            fac = Facility(name=fname)
            db.add(fac)
            facility_objs.append(fac)
        db.flush()

        # 6. Seed Users: Admin, Coordinators, HODs, Faculty
        print("👤 Seeding Users (Admin, Coordinators, HODs, Faculty)...")
        # One Admin (admin@git.edu / Admin@123)
        admin = User(
            name="System Administrator",
            email="admin@git.edu",
            password_hash=hash_password("Admin@123"),
            role=UserRole.ADMIN,
            phone="+91 9876543210",
            is_active=True,
        )
        db.add(admin)
        db.flush()

        # 6 HODs (one for each department)
        hod_info = [
            ("Dr. Arvind Rao", "hod.cse@git.edu", "CSE", "+91 9876543211"),
            ("Dr. Priya Sharma", "hod.ece@git.edu", "ECE", "+91 9876543212"),
            ("Dr. Meenakshi Sundaram", "hod.ise@git.edu", "ISE", "+91 9876543213"),
            ("Dr. Rajesh Kulkarni", "hod.mech@git.edu", "MECH", "+91 9876543214"),
            ("Dr. Suresh Patil", "hod.civil@git.edu", "CIVIL", "+91 9876543215"),
            ("Dr. Vikram Joshi", "hod.mba@git.edu", "MBA", "+91 9876543216"),
        ]
        hod_users = []
        for name, email, code, phone in hod_info:
            hod = User(
                name=name,
                email=email,
                password_hash=hash_password("Hod@123"),
                role=UserRole.HOD,
                department_id=dept_objs[code].id,
                phone=phone,
                is_active=True,
            )
            db.add(hod)
            hod_users.append(hod)
        db.flush()

        # 4 Coordinators (one assigned per block)
        coord_info = [
            ("Prof. Ananya Sen", "coordinator.block_a@git.edu", 0, "+91 9876543221"),
            ("Prof. Rohan Verma", "coordinator.block_b@git.edu", 1, "+91 9876543222"),
            ("Prof. Kavita Nair", "coordinator.block_c@git.edu", 2, "+91 9876543223"),
            ("Prof. Dinesh Hegde", "coordinator.block_d@git.edu", 3, "+91 9876543224"),
        ]
        coord_users = []
        for name, email, block_idx, phone in coord_info:
            coord = User(
                name=name,
                email=email,
                password_hash=hash_password("Coord@123"),
                role=UserRole.COORDINATOR,
                phone=phone,
                is_active=True,
            )
            db.add(coord)
            db.flush()
            coord_users.append(coord)

            # Assign to Block
            assignment = BlockCoordinator(user_id=coord.id, block_id=block_objs[block_idx].id)
            db.add(assignment)
        db.flush()

        # Guarantee every coordinator has at least one assigned block
        all_coordinators = db.query(User).filter(User.role == UserRole.COORDINATOR).all()
        for c in all_coordinators:
            assigned = db.query(BlockCoordinator).filter(BlockCoordinator.user_id == c.id).first()
            if not assigned and block_objs:
                db.add(BlockCoordinator(user_id=c.id, block_id=block_objs[0].id))
        db.flush()

        # Sample Faculty Members
        faculty_info = [
            ("Dr. Amit Roy", "faculty.cse@git.edu", "CSE"),
            ("Prof. Neha Gupta", "faculty.ece@git.edu", "ECE"),
            ("Dr. Sandeep Mane", "faculty.mech@git.edu", "MECH"),
            ("Prof. Pooja Deshmukh", "faculty.civil@git.edu", "CIVIL"),
            ("Dr. Karthik Bhat", "faculty.ise@git.edu", "ISE"),
            ("Prof. Swati Joshi", "faculty.mba@git.edu", "MBA"),
        ]
        faculty_users = []
        for name, email, code in faculty_info:
            fac_user = User(
                name=name,
                email=email,
                password_hash=hash_password("Faculty@123"),
                role=UserRole.FACULTY,
                department_id=dept_objs[code].id,
                phone="+91 9876543230",
                is_active=True,
            )
            db.add(fac_user)
            faculty_users.append(fac_user)
        db.flush()

        # 7. Seed ~40 Rooms across 4 Blocks
        print("🚪 Seeding 40 Rooms with varied capacities and facilities...")
        rooms_list = []
        room_configs = [
            # Block A: 10 Rooms (Main Academic: Classrooms, Seminar Hall, Exam Hall)
            ("A-101", 0, 1, RoomType.CLASSROOM, 60, "CSE", RoomStatus.ACTIVE, None, [0, 1, 5, 8]),
            ("A-102", 0, 1, RoomType.CLASSROOM, 60, "CSE", RoomStatus.ACTIVE, None, [0, 1, 5, 8]),
            ("A-103", 0, 1, RoomType.CLASSROOM, 45, "ISE", RoomStatus.ACTIVE, None, [0, 5, 8]),
            ("A-201", 0, 2, RoomType.CLASSROOM, 75, "ECE", RoomStatus.ACTIVE, None, [0, 1, 2, 5, 8, 14]),
            ("A-202", 0, 2, RoomType.CLASSROOM, 75, "ECE", RoomStatus.ACTIVE, None, [0, 1, 2, 5, 8, 14]),
            ("A-203", 0, 2, RoomType.CLASSROOM, 60, "MECH", RoomStatus.ACTIVE, None, [0, 5, 8]),
            ("A-301", 0, 3, RoomType.SEMINAR_HALL, 150, None, RoomStatus.ACTIVE, None, [0, 1, 4, 5, 7, 10, 12, 13, 14]),
            ("A-302", 0, 3, RoomType.CLASSROOM, 60, "CIVIL", RoomStatus.ACTIVE, None, [0, 5, 8]),
            ("A-401", 0, 4, RoomType.EXAM_HALL, 180, None, RoomStatus.ACTIVE, None, [1, 5, 10, 11]),
            ("A-402", 0, 4, RoomType.CLASSROOM, 50, None, RoomStatus.MAINTENANCE, "HVAC system under annual servicing", [0, 8]),

            # Block B: 10 Rooms (Computing & Tech: Labs and Classrooms)
            ("B-101", 1, 1, RoomType.LAB, 40, "CSE", RoomStatus.ACTIVE, None, [0, 1, 3, 5, 9, 10]),
            ("B-102", 1, 1, RoomType.LAB, 40, "CSE", RoomStatus.ACTIVE, None, [0, 1, 3, 5, 9, 10]),
            ("B-103", 1, 1, RoomType.LAB, 35, "ISE", RoomStatus.ACTIVE, None, [0, 1, 3, 5, 9, 10]),
            ("B-201", 1, 2, RoomType.LAB, 45, "ISE", RoomStatus.ACTIVE, None, [0, 1, 2, 3, 5, 9, 10]),
            ("B-202", 1, 2, RoomType.CLASSROOM, 60, "CSE", RoomStatus.ACTIVE, None, [0, 1, 2, 5, 8]),
            ("B-203", 1, 2, RoomType.CLASSROOM, 60, "ISE", RoomStatus.ACTIVE, None, [0, 1, 5, 8]),
            ("B-301", 1, 3, RoomType.LAB, 50, "CSE", RoomStatus.ACTIVE, None, [0, 1, 3, 5, 7, 9, 10]),
            ("B-302", 1, 3, RoomType.CLASSROOM, 70, None, RoomStatus.ACTIVE, None, [0, 1, 5, 8, 14]),
            ("B-401", 1, 4, RoomType.SEMINAR_HALL, 120, "CSE", RoomStatus.ACTIVE, None, [0, 1, 4, 5, 7, 12, 13]),
            ("B-402", 1, 4, RoomType.CLASSROOM, 40, None, RoomStatus.ACTIVE, None, [0, 5, 8]),

            # Block C: 10 Rooms (Core Engineering: Mech, Civil, Labs)
            ("C-101", 2, 1, RoomType.LAB, 30, "MECH", RoomStatus.ACTIVE, None, [0, 5, 9, 10]),
            ("C-102", 2, 1, RoomType.LAB, 35, "CIVIL", RoomStatus.ACTIVE, None, [0, 5, 9, 10]),
            ("C-103", 2, 1, RoomType.CLASSROOM, 65, "MECH", RoomStatus.ACTIVE, None, [0, 5, 8]),
            ("C-201", 2, 2, RoomType.LAB, 40, "ECE", RoomStatus.ACTIVE, None, [0, 1, 5, 9, 10]),
            ("C-202", 2, 2, RoomType.CLASSROOM, 70, "CIVIL", RoomStatus.ACTIVE, None, [0, 5, 8, 14]),
            ("C-203", 2, 2, RoomType.CLASSROOM, 70, "MECH", RoomStatus.ACTIVE, None, [0, 5, 8, 14]),
            ("C-301", 2, 3, RoomType.EXAM_HALL, 200, None, RoomStatus.ACTIVE, None, [1, 5, 10, 11]),
            ("C-302", 2, 3, RoomType.CLASSROOM, 55, "ECE", RoomStatus.ACTIVE, None, [0, 5, 8]),
            ("C-401", 2, 4, RoomType.CLASSROOM, 50, None, RoomStatus.MAINTENANCE, "Projector replacement and ceiling rewiring", [0, 8]),
            ("C-402", 2, 4, RoomType.LAB, 40, "ECE", RoomStatus.ACTIVE, None, [0, 1, 5, 9, 10]),

            # Block D: 10 Rooms (PG & Innovation: MBA, Research, Auditoriums)
            ("D-101", 3, 1, RoomType.CLASSROOM, 60, "MBA", RoomStatus.ACTIVE, None, [0, 1, 2, 5, 8, 14]),
            ("D-102", 3, 1, RoomType.CLASSROOM, 60, "MBA", RoomStatus.ACTIVE, None, [0, 1, 2, 5, 8, 14]),
            ("D-103", 3, 1, RoomType.LAB, 35, "MBA", RoomStatus.ACTIVE, None, [0, 1, 3, 5, 10]),
            ("D-201", 3, 2, RoomType.CLASSROOM, 50, "MBA", RoomStatus.ACTIVE, None, [0, 1, 5, 8]),
            ("D-202", 3, 2, RoomType.CLASSROOM, 50, None, RoomStatus.ACTIVE, None, [0, 1, 5, 8]),
            ("D-203", 3, 2, RoomType.CLASSROOM, 60, None, RoomStatus.ACTIVE, None, [0, 1, 5, 8]),
            ("D-301", 3, 3, RoomType.SEMINAR_HALL, 250, None, RoomStatus.ACTIVE, None, [0, 1, 2, 4, 5, 7, 8, 10, 12, 13, 14]),
            ("D-302", 3, 3, RoomType.EXAM_HALL, 160, None, RoomStatus.ACTIVE, None, [1, 5, 10, 11]),
            ("D-401", 3, 4, RoomType.CLASSROOM, 45, None, RoomStatus.ACTIVE, None, [0, 1, 5, 8]),
            ("D-402", 3, 4, RoomType.LAB, 40, "CSE", RoomStatus.ACTIVE, None, [0, 1, 3, 5, 7, 9, 10]),
        ]

        for name, blk_idx, floor, rtype, cap, dept_code, status, note, fac_indices in room_configs:
            dept_id = dept_objs[dept_code].id if dept_code else None
            room = Room(
                name=name,
                block_id=block_objs[blk_idx].id,
                floor=floor,
                room_type=rtype,
                capacity=cap,
                department_id=dept_id,
                status=status,
                maintenance_note=note,
            )
            db.add(room)
            db.flush()
            rooms_list.append(room)

            # Assign facilities
            for fidx in fac_indices:
                rf = RoomFacility(room_id=room.id, facility_id=facility_objs[fidx].id)
                db.add(rf)
        db.flush()

        # 8. Seed Weekly Timetable for ~60% of room-slots
        # 40 rooms, 5 days (Monday-Friday = 0..4), 8 slots per day = 1600 total room-slots
        # 60% = ~960 entries
        print("📅 Seeding weekly timetable for ~60% of room-slots (Monday to Friday)...")
        random.seed(42)  # Deterministic generation

        subjects_by_dept = {
            "CSE": [
                ("Data Structures & Algorithms", "Dr. Arvind Rao"),
                ("Database Management Systems", "Dr. Amit Roy"),
                ("Operating Systems & Linux Kernel", "Prof. Sneha Deshpande"),
                ("Computer Networks & Protocols", "Dr. Arvind Rao"),
                ("Compiler Design & Automata", "Dr. Amit Roy"),
                ("Machine Learning Foundations", "Prof. Sneha Deshpande"),
            ],
            "ECE": [
                ("Digital Signal Processing", "Dr. Priya Sharma"),
                ("VLSI Design & Embedded Systems", "Prof. Neha Gupta"),
                ("Analog Circuits & Amplifiers", "Dr. Priya Sharma"),
                ("Microcontrollers & IoT", "Prof. Neha Gupta"),
                ("Communication Theory", "Dr. Priya Sharma"),
            ],
            "ISE": [
                ("Object Oriented Software Design", "Dr. Meenakshi Sundaram"),
                ("Cloud Computing & DevOps", "Dr. Karthik Bhat"),
                ("Web Technologies & Microservices", "Dr. Karthik Bhat"),
                ("Information Security & Cryptography", "Dr. Meenakshi Sundaram"),
            ],
            "MECH": [
                ("Fluid Dynamics & Hydraulics", "Dr. Rajesh Kulkarni"),
                ("Thermodynamics & Heat Transfer", "Dr. Sandeep Mane"),
                ("Kinematics of Machinery", "Dr. Rajesh Kulkarni"),
                ("Manufacturing Engineering", "Dr. Sandeep Mane"),
            ],
            "CIVIL": [
                ("Structural Analysis & Mechanics", "Dr. Suresh Patil"),
                ("Geotechnical Engineering", "Prof. Pooja Deshmukh"),
                ("Environmental Science & Water Mgmt", "Dr. Suresh Patil"),
                ("Transportation Engineering", "Prof. Pooja Deshmukh"),
            ],
            "MBA": [
                ("Marketing Analytics & Consumer Behaviour", "Dr. Vikram Joshi"),
                ("Corporate Finance & Valuations", "Prof. Swati Joshi"),
                ("Organizational Behaviour & HR", "Dr. Vikram Joshi"),
                ("Operations & Supply Chain Logistics", "Prof. Swati Joshi"),
            ],
        }

        timetable_count = 0
        days_of_week = [0, 1, 2, 3, 4]  # Mon to Fri

        # Active rooms eligible for classes (exclude maintenance)
        active_rooms = [r for r in rooms_list if r.status == RoomStatus.ACTIVE]

        for room in active_rooms:
            # Determine suitable department for the subjects
            if room.department_id:
                # Find department code
                dept_code = next(k for k, v in dept_objs.items() if v.id == room.department_id)
            else:
                dept_code = random.choice(list(dept_objs.keys()))

            dept = dept_objs[dept_code]
            dept_subjects = subjects_by_dept[dept_code]

            for day in days_of_week:
                for slot in slot_objs:
                    # Target ~60% occupancy probability
                    if random.random() < 0.60:
                        subject, faculty = random.choice(dept_subjects)
                        entry = TimetableEntry(
                            room_id=room.id,
                            day_of_week=day,
                            slot_id=slot.id,
                            department_id=dept.id,
                            subject=subject,
                            faculty_name=faculty,
                        )
                        db.add(entry)
                        timetable_count += 1

        db.commit()

        total_possible_slots = len(active_rooms) * len(days_of_week) * len(slot_objs)
        percentage = (timetable_count / total_possible_slots) * 100

        print(f"✅ Seeding finished successfully!")
        print(f"   - Departments: {len(dept_objs)}")
        print(f"   - Blocks: {len(block_objs)}")
        print(f"   - Time Slots: {len(slot_objs)}")
        print(f"   - Facilities: {len(facility_objs)}")
        print(f"   - Rooms: {len(rooms_list)} ({len(active_rooms)} active)")
        print(f"   - Admin User: admin@git.edu (Admin@123)")
        print(f"   - HOD Users: {len(hod_users)}")
        print(f"   - Coordinator Users: {len(coord_users)}")
        print(f"   - Faculty Users: {len(faculty_users)}")
        print(f"   - Timetable Entries: {timetable_count}/{total_possible_slots} ({percentage:.1f}% room-slot coverage)")

    except Exception as e:
        db.rollback()
        print(f"❌ Error during seeding: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()

