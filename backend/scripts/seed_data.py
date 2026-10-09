import sys
import os
from datetime import date, time, datetime, timedelta, timezone

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from app.database.connection import SessionLocal, engine
from app.database.base import Base
from app.models.department import Department
from app.models.building import Building
from app.models.classroom import Classroom
from app.models.facility import Facility
from app.models.classroom_facility import ClassroomFacility
from app.models.room_department_access import RoomDepartmentAccess
from app.models.class_group import ClassGroup
from app.models.class_session import ClassSession
from app.models.session_facility import SessionFacility
from app.models.room_unavailability import RoomUnavailability
from app.models.booking import Booking
from app.models.user import User
from app.core.security import get_password_hash


def seed():
    print("Seeding database...")
    db: Session = SessionLocal()

    try:
        # 1. Clean existing sample data (in reverse dependency order)
        db.execute(delete(Booking))
        db.execute(delete(RoomUnavailability))
        db.execute(delete(SessionFacility))
        db.execute(delete(ClassSession))
        db.execute(delete(ClassGroup))
        db.execute(delete(RoomDepartmentAccess))
        db.execute(delete(ClassroomFacility))
        db.execute(delete(Classroom))
        db.execute(delete(Facility))
        db.execute(delete(Building))
        db.execute(delete(Department))
        db.execute(delete(User))
        db.commit()

        # 2. Seed Admin User
        admin_user = User(
            username="admin",
            email="admin@college.edu",
            hashed_password=get_password_hash("admin123"),
            role="ADMIN",
            is_active=True,
        )
        db.add(admin_user)
        db.commit()
        print("✓ Created admin user (admin / admin123)")

        # 3. Seed Departments (CSE, ECE, MECH)
        dept_cse = Department(name="Computer Science and Engineering", code="CSE")
        dept_ece = Department(name="Electronics and Communication Engineering", code="ECE")
        dept_mech = Department(name="Mechanical Engineering", code="MECH")
        db.add_all([dept_cse, dept_ece, dept_mech])
        db.commit()
        db.refresh(dept_cse)
        db.refresh(dept_ece)
        db.refresh(dept_mech)
        print("✓ Seeded Departments: CSE, ECE, MECH")

        # Create HOD users for departments
        hod_cse = User(username="hod_cse", email="hod_cse@college.edu", hashed_password=get_password_hash("hod123"), role="HOD", department_id=dept_cse.id)
        hod_ece = User(username="hod_ece", email="hod_ece@college.edu", hashed_password=get_password_hash("hod123"), role="HOD", department_id=dept_ece.id)
        hod_mech = User(username="hod_mech", email="hod_mech@college.edu", hashed_password=get_password_hash("hod123"), role="HOD", department_id=dept_mech.id)
        db.add_all([hod_cse, hod_ece, hod_mech])
        db.commit()
        print("✓ Created HOD users for departments")

        from app.models.approval_policy import ApprovalPolicy
        db.execute(delete(ApprovalPolicy))
        db.add_all([
            ApprovalPolicy(purpose="REGULAR_CLASS", requires_hod_approval=False),
            ApprovalPolicy(purpose="EXAMINATION", requires_hod_approval=True),
            ApprovalPolicy(purpose="MCQ_TEST", requires_hod_approval=True),
            ApprovalPolicy(purpose="SEMINAR", requires_hod_approval=False),
            ApprovalPolicy(purpose="WORKSHOP", requires_hod_approval=False),
            ApprovalPolicy(purpose="EVENT", requires_hod_approval=False),
            ApprovalPolicy(purpose="OTHER", requires_hod_approval=False),
        ])
        db.commit()
        print("✓ Created Approval Policies")

        # 4. Seed Building
        main_building = Building(name="Main Academic Block", location="North Campus")
        tech_building = Building(name="Technology Block", location="South Campus")
        db.add_all([main_building, tech_building])
        db.commit()
        print("✓ Seeded Buildings: Main Academic Block, Technology Block")

        # 5. Seed Facilities
        fac_projector = Facility(name="Projector", description="High-definition multimedia projector")
        fac_computer = Facility(name="Computer", description="Individual workstation with development environment")
        fac_smart_board = Facility(name="Smart Board", description="Interactive digital touch whiteboard")
        db.add_all([fac_projector, fac_computer, fac_smart_board])
        db.commit()
        print("✓ Seeded Facilities: Projector, Computer, Smart Board")

        # 6. Seed Classrooms
        # Room 101, capacity 40
        room_101 = Classroom(
            name="Room 101",
            building_id=main_building.id,
            capacity=40,
            room_type="CLASSROOM",
            location_description="1st Floor, Main Block",
            is_active=True,
        )
        # Room 102, capacity 60
        room_102 = Classroom(
            name="Room 102",
            building_id=main_building.id,
            capacity=60,
            room_type="CLASSROOM",
            location_description="1st Floor, Main Block",
            is_active=True,
        )
        # Room 201, capacity 80
        room_201 = Classroom(
            name="Room 201",
            building_id=main_building.id,
            capacity=80,
            room_type="CLASSROOM",
            location_description="2nd Floor, Main Block",
            is_active=True,
        )
        # CSE Computer Lab, capacity 35, authorized for CSE
        lab_cse = Classroom(
            name="CSE Computer Lab",
            building_id=tech_building.id,
            capacity=35,
            room_type="LAB",
            location_description="Ground Floor, Tech Block",
            is_active=True,
        )
        # Electronics Lab, capacity 30, authorized for ECE
        lab_ece = Classroom(
            name="Electronics Lab",
            building_id=tech_building.id,
            capacity=30,
            room_type="LAB",
            location_description="1st Floor, Tech Block",
            is_active=True,
        )
        # Shared Computer Lab, capacity 40, authorized for CSE and ECE
        lab_shared = Classroom(
            name="Shared Computer Lab",
            building_id=tech_building.id,
            capacity=40,
            room_type="LAB",
            location_description="2nd Floor, Tech Block",
            is_active=True,
        )

        db.add_all([room_101, room_102, room_201, lab_cse, lab_ece, lab_shared])
        db.commit()

        # 7. Map Facilities to Classrooms
        # Room 101: Projector
        db.add(ClassroomFacility(classroom_id=room_101.id, facility_id=fac_projector.id))
        # Room 102: Projector, Smart Board
        db.add(ClassroomFacility(classroom_id=room_102.id, facility_id=fac_projector.id))
        db.add(ClassroomFacility(classroom_id=room_102.id, facility_id=fac_smart_board.id))
        # Room 201: Projector
        db.add(ClassroomFacility(classroom_id=room_201.id, facility_id=fac_projector.id))
        # CSE Computer Lab: Computer, Projector
        db.add(ClassroomFacility(classroom_id=lab_cse.id, facility_id=fac_computer.id))
        db.add(ClassroomFacility(classroom_id=lab_cse.id, facility_id=fac_projector.id))
        # Electronics Lab: Computer, Smart Board
        db.add(ClassroomFacility(classroom_id=lab_ece.id, facility_id=fac_computer.id))
        db.add(ClassroomFacility(classroom_id=lab_ece.id, facility_id=fac_smart_board.id))
        # Shared Lab: Computer, Projector, Smart Board
        db.add(ClassroomFacility(classroom_id=lab_shared.id, facility_id=fac_computer.id))
        db.add(ClassroomFacility(classroom_id=lab_shared.id, facility_id=fac_projector.id))
        db.add(ClassroomFacility(classroom_id=lab_shared.id, facility_id=fac_smart_board.id))
        db.commit()
        print("✓ Seeded Classrooms and mapped facilities")

        # 8. Configure Lab Department Access
        # CSE Computer Lab -> authorized for CSE
        db.add(RoomDepartmentAccess(room_id=lab_cse.id, department_id=dept_cse.id))
        # Electronics Lab -> authorized for ECE
        db.add(RoomDepartmentAccess(room_id=lab_ece.id, department_id=dept_ece.id))
        # Shared Computer Lab -> authorized for CSE and ECE
        db.add(RoomDepartmentAccess(room_id=lab_shared.id, department_id=dept_cse.id))
        db.add(RoomDepartmentAccess(room_id=lab_shared.id, department_id=dept_ece.id))
        db.commit()
        print("✓ Seeded Lab Department Access permissions")

        # 9. Seed Class Groups
        cg_cse_a = ClassGroup(name="CSE Year 2 Sec A", department_id=dept_cse.id, student_count=35)
        cg_cse_b = ClassGroup(name="CSE Year 3 Sec B", department_id=dept_cse.id, student_count=55)
        cg_ece_a = ClassGroup(name="ECE Year 2 Sec A", department_id=dept_ece.id, student_count=28)
        cg_mech_a = ClassGroup(name="MECH Year 3 Sec A", department_id=dept_mech.id, student_count=70)
        db.add_all([cg_cse_a, cg_cse_b, cg_ece_a, cg_mech_a])
        db.commit()
        print("✓ Seeded Class Groups")

        # 10. Seed Scenarios
        # Date anchor: Next Monday
        today = date.today()
        target_date = today + timedelta(days=(7 - today.weekday()))

        # Scenario 1: Feasible Regular Class Sessions (9:00 - 10:30)
        s1 = ClassSession(
            class_group_id=cg_cse_b.id,  # 55 students
            session_date=target_date,
            start_time=time(9, 0),
            end_time=time(10, 30),
            required_room_type="CLASSROOM",
            notes="Algorithms Lecture (Needs Projector)",
        )
        s2 = ClassSession(
            class_group_id=cg_mech_a.id,  # 70 students -> fits Room 201 (80)
            session_date=target_date,
            start_time=time(9, 0),
            end_time=time(10, 30),
            required_room_type="CLASSROOM",
            notes="Thermodynamics Lecture",
        )
        db.add_all([s1, s2])
        db.flush()
        db.add(SessionFacility(session_id=s1.id, facility_id=fac_projector.id))
        db.add(SessionFacility(session_id=s2.id, facility_id=fac_projector.id))

        # Scenario 2: Feasible Lab Sessions (11:00 - 13:00)
        s3_lab = ClassSession(
            class_group_id=cg_cse_a.id,  # 35 students -> fits CSE Lab or Shared Lab
            session_date=target_date,
            start_time=time(11, 0),
            end_time=time(13, 0),
            required_room_type="LAB",
            notes="OS Programming Lab (CSE authorized)",
        )
        s4_lab = ClassSession(
            class_group_id=cg_ece_a.id,  # 28 students -> fits Electronics Lab or Shared Lab
            session_date=target_date,
            start_time=time(11, 0),
            end_time=time(13, 0),
            required_room_type="LAB",
            notes="VLSI Design Lab (ECE authorized)",
        )
        db.add_all([s3_lab, s4_lab])
        db.flush()
        db.add(SessionFacility(session_id=s3_lab.id, facility_id=fac_computer.id))
        db.add(SessionFacility(session_id=s4_lab.id, facility_id=fac_computer.id))

        # Scenario 3: Room Contention Scenario (14:00 - 15:30)
        # Multiple large groups competing for the single 80-capacity room (Room 201)
        s5_contention_1 = ClassSession(
            class_group_id=cg_mech_a.id,  # 70 students
            session_date=target_date,
            start_time=time(14, 0),
            end_time=time(15, 30),
            required_room_type="CLASSROOM",
            notes="Contention Lecture 1",
        )
        cg_large_cse = ClassGroup(name="CSE Combined Elective", department_id=dept_cse.id, student_count=75)
        db.add(cg_large_cse)
        db.flush()
        s6_contention_2 = ClassSession(
            class_group_id=cg_large_cse.id,  # 75 students
            session_date=target_date,
            start_time=time(14, 0),
            end_time=time(15, 30),
            required_room_type="CLASSROOM",
            notes="Contention Lecture 2 (Only 1 room with cap >= 75)",
        )
        db.add_all([s5_contention_1, s6_contention_2])

        # Scenario 4: No Suitable Lab Scenario (16:00 - 17:30)
        # MECH group requesting a LAB, but no labs are authorized for MECH!
        s7_infeasible_lab = ClassSession(
            class_group_id=cg_mech_a.id,  # MECH department
            session_date=target_date,
            start_time=time(16, 0),
            end_time=time(17, 30),
            required_room_type="LAB",
            notes="Robotics Lab for MECH (Unauthorized on all existing labs)",
        )
        db.add(s7_infeasible_lab)

        db.commit()
        print(f"✓ Seeded class sessions for date {target_date}")
        print("✓ All 4 scenarios initialized: Feasible, Contention, Infeasible Lab, Reallocation ready.")
        print("\nSeed completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()

