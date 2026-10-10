from datetime import date, datetime, time, timezone
import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.block import Block
from app.models.booking import Booking
from app.models.department import Department
from app.models.enums import BookingStatus, RequesterType, RoomStatus, RoomType, UserRole
from app.models.facility import Facility
from app.models.room import Room
from app.models.time_slot import TimeSlot
from app.models.timetable import TimetableEntry
from app.models.user import User


def get_auth_headers(user: User) -> dict:
    """Generate Authorization header for a user."""
    token = create_access_token(
        subject=user.id,
        extra_claims={"email": user.email, "role": user.role.value},
    )
    return {"Authorization": f"Bearer {token}"}


# -------------------------------------------------------------
# 1. Authorization & Role Verification
# -------------------------------------------------------------

def test_admin_routes_require_authentication(client: TestClient):
    """Unauthenticated calls to /api/admin/* should return 401."""
    endpoints = [
        "/api/admin/users",
        "/api/admin/departments",
        "/api/admin/blocks",
        "/api/admin/facilities",
        "/api/admin/rooms",
        "/api/admin/time-slots",
        "/api/admin/timetable",
        "/api/admin/bookings",
        "/api/admin/audit-logs",
    ]
    for ep in endpoints:
        resp = client.get(ep)
        assert resp.status_code == 401, f"Expected 401 for unauthenticated {ep}, got {resp.status_code}"


def test_admin_routes_forbidden_for_non_admin(client: TestClient, seed_users):
    """Authenticated calls by non-admin staff (COORDINATOR, FACULTY) should return 403."""
    coord_headers = get_auth_headers(seed_users["coordinator"])
    faculty_headers = get_auth_headers(seed_users["faculty"])

    endpoints = [
        "/api/admin/users",
        "/api/admin/departments",
        "/api/admin/blocks",
        "/api/admin/facilities",
        "/api/admin/rooms",
        "/api/admin/time-slots",
        "/api/admin/timetable",
        "/api/admin/bookings",
        "/api/admin/audit-logs",
    ]
    for ep in endpoints:
        assert client.get(ep, headers=coord_headers).status_code == 403
        assert client.get(ep, headers=faculty_headers).status_code == 403


# -------------------------------------------------------------
# 2. User Management
# -------------------------------------------------------------

def test_admin_user_crud_and_lifecycle(client: TestClient, seed_users, db_session: Session):
    admin_headers = get_auth_headers(seed_users["admin"])

    # Setup department for user
    dept = Department(name="Computer Science", code="CS", hod_approval_required=True)
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)

    # 1. Create HOD user
    create_payload = {
        "name": "Dr. Alan Turing",
        "email": "alan.turing@college.edu",
        "role": UserRole.HOD.value,
        "department_id": dept.id,
        "phone": "+1-555-0199",
    }
    resp = client.post("/api/admin/users", json=create_payload, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["email"] == "alan.turing@college.edu"
    assert created["role"] == UserRole.HOD.value
    assert created["must_change_password"] is True
    assert "temporary_password" in created
    temp_pwd = created["temporary_password"]
    user_id = created["id"]

    # 2. Attempt duplicate creation -> 409
    dup_resp = client.post("/api/admin/users", json=create_payload, headers=admin_headers)
    assert dup_resp.status_code == 409

    # 3. Create user with invalid department -> 404
    invalid_dept_payload = {
        "name": "Invalid Dept User",
        "email": "invalid.dept@college.edu",
        "role": UserRole.FACULTY.value,
        "department_id": 99999,
    }
    assert client.post("/api/admin/users", json=invalid_dept_payload, headers=admin_headers).status_code == 404

    # 4. List users with search and filters
    list_resp = client.get("/api/admin/users?search=turing&role=HOD", headers=admin_headers)
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] == 1
    assert list_data["items"][0]["id"] == user_id

    # 5. Get user by ID
    get_resp = client.get(f"/api/admin/users/{user_id}", headers=admin_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Dr. Alan Turing"

    # 6. Update user
    update_resp = client.patch(
        f"/api/admin/users/{user_id}",
        json={"name": "Prof. Alan M. Turing", "phone": "+1-555-0200"},
        headers=admin_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Prof. Alan M. Turing"

    # 7. Deactivate user
    deact_resp = client.post(f"/api/admin/users/{user_id}/deactivate", headers=admin_headers)
    assert deact_resp.status_code == 200
    assert deact_resp.json()["is_active"] is False

    # 8. Reactivate user
    act_resp = client.post(f"/api/admin/users/{user_id}/activate", headers=admin_headers)
    assert act_resp.status_code == 200
    assert act_resp.json()["is_active"] is True

    # 9. Test First-Login Flow & Password Change
    # Log in as HOD using temp_password
    hod_login_resp = client.post(
        "/api/auth/hod/login",
        json={"email": "alan.turing@college.edu", "password": temp_pwd},
    )
    assert hod_login_resp.status_code == 200
    hod_token = hod_login_resp.json()["access_token"]
    assert hod_login_resp.json()["user"]["must_change_password"] is True

    # Change password
    change_pwd_resp = client.post(
        "/api/auth/change-password",
        json={"old_password": temp_pwd, "new_password": "NewSecurePassword123!"},
        headers={"Authorization": f"Bearer {hod_token}"},
    )
    assert change_pwd_resp.status_code == 200

    # User's must_change_password should now be False
    refreshed_user = client.get(f"/api/admin/users/{user_id}", headers=admin_headers).json()
    assert refreshed_user["must_change_password"] is False


# -------------------------------------------------------------
# 3. Department Management
# -------------------------------------------------------------

def test_department_crud_and_toggle(client: TestClient, seed_users):
    admin_headers = get_auth_headers(seed_users["admin"])

    # 1. Create department
    dept_payload = {
        "name": "Electronics & Communication",
        "code": "ECE",
        "hod_approval_required": True,
    }
    resp = client.post("/api/admin/departments", json=dept_payload, headers=admin_headers)
    assert resp.status_code == 201
    dept_id = resp.json()["id"]
    assert resp.json()["code"] == "ECE"
    assert resp.json()["hod_approval_required"] is True

    # 2. Duplicate code -> 409
    dup_resp = client.post("/api/admin/departments", json=dept_payload, headers=admin_headers)
    assert dup_resp.status_code == 409

    # 3. List departments
    list_resp = client.get("/api/admin/departments?search=ECE", headers=admin_headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. Toggle HOD approval required
    toggle_resp = client.post(
        f"/api/admin/departments/{dept_id}/toggle-hod-approval",
        headers=admin_headers,
    )
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["hod_approval_required"] is False

    # Toggle back to True
    toggle_back = client.patch(
        f"/api/admin/departments/{dept_id}/toggle-hod-approval",
        headers=admin_headers,
    )
    assert toggle_back.status_code == 200
    assert toggle_back.json()["hod_approval_required"] is True

    # 5. Update department
    update_resp = client.patch(
        f"/api/admin/departments/{dept_id}",
        json={"name": "Electronics and Electrical"},
        headers=admin_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Electronics and Electrical"

    # 6. Delete department
    del_resp = client.delete(f"/api/admin/departments/{dept_id}", headers=admin_headers)
    assert del_resp.status_code == 200

    # 7. Verify deletion
    assert client.get(f"/api/admin/departments/{dept_id}", headers=admin_headers).status_code == 404


# -------------------------------------------------------------
# 4. Block Management & Coordinator Assignment
# -------------------------------------------------------------

def test_block_crud_and_coordinator_assignment(client: TestClient, seed_users):
    admin_headers = get_auth_headers(seed_users["admin"])
    coord_user = seed_users["coordinator"]
    faculty_user = seed_users["faculty"]

    # 1. Create Block
    block_payload = {"name": "Science Block A", "description": "Physics and Chemistry labs"}
    resp = client.post("/api/admin/blocks", json=block_payload, headers=admin_headers)
    assert resp.status_code == 201
    block_id = resp.json()["id"]
    assert resp.json()["name"] == "Science Block A"

    # 2. Duplicate block -> 409
    assert client.post("/api/admin/blocks", json=block_payload, headers=admin_headers).status_code == 409

    # 3. Assign non-coordinator -> 400
    invalid_assign = client.post(
        f"/api/admin/blocks/{block_id}/coordinators",
        json={"user_id": faculty_user.id},
        headers=admin_headers,
    )
    assert invalid_assign.status_code == 400

    # 4. Assign coordinator -> 200
    assign_resp = client.post(
        f"/api/admin/blocks/{block_id}/coordinators",
        json={"user_id": coord_user.id},
        headers=admin_headers,
    )
    assert assign_resp.status_code == 200
    block_data = assign_resp.json()
    assert any(c["id"] == coord_user.id for c in block_data["coordinators"])

    # 5. Duplicate assignment -> 409
    dup_assign = client.post(
        f"/api/admin/blocks/{block_id}/coordinators",
        json={"user_id": coord_user.id},
        headers=admin_headers,
    )
    assert dup_assign.status_code == 409

    # 6. Unassign coordinator
    unassign_resp = client.delete(
        f"/api/admin/blocks/{block_id}/coordinators/{coord_user.id}",
        headers=admin_headers,
    )
    assert unassign_resp.status_code == 200
    assert not any(c["id"] == coord_user.id for c in unassign_resp.json()["coordinators"])

    # 7. Delete block
    del_resp = client.delete(f"/api/admin/blocks/{block_id}", headers=admin_headers)
    assert del_resp.status_code == 200
    assert client.get(f"/api/admin/blocks/{block_id}", headers=admin_headers).status_code == 404


# -------------------------------------------------------------
# 5. Facility Management
# -------------------------------------------------------------

def test_facility_crud(client: TestClient, seed_users):
    admin_headers = get_auth_headers(seed_users["admin"])

    # 1. Create facility
    resp = client.post("/api/admin/facilities", json={"name": "4K Projector"}, headers=admin_headers)
    assert resp.status_code == 201
    fac_id = resp.json()["id"]
    assert resp.json()["name"] == "4K Projector"

    # 2. Duplicate -> 409
    assert client.post("/api/admin/facilities", json={"name": "4K Projector"}, headers=admin_headers).status_code == 409

    # 3. List facilities
    list_resp = client.get("/api/admin/facilities?search=Projector", headers=admin_headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. Update facility
    update_resp = client.patch(f"/api/admin/facilities/{fac_id}", json={"name": "Laser Projector"}, headers=admin_headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Laser Projector"

    # 5. Delete facility
    del_resp = client.delete(f"/api/admin/facilities/{fac_id}", headers=admin_headers)
    assert del_resp.status_code == 200
    assert client.get(f"/api/admin/facilities/{fac_id}", headers=admin_headers).status_code == 404


# -------------------------------------------------------------
# 6. Room Management & Status / Lab Validation
# -------------------------------------------------------------

def test_room_crud_and_status(client: TestClient, seed_users, db_session: Session):
    admin_headers = get_auth_headers(seed_users["admin"])

    # Setup prerequisites: block, department, facilities
    block = Block(name="Academic Block C")
    dept = Department(name="Information Science", code="ISE", hod_approval_required=True)
    fac1 = Facility(name="High-speed WiFi")
    fac2 = Facility(name="Air Conditioning")
    db_session.add_all([block, dept, fac1, fac2])
    db_session.commit()
    db_session.refresh(block)
    db_session.refresh(dept)
    db_session.refresh(fac1)
    db_session.refresh(fac2)

    # 1. Validation: Capacity must be > 0
    invalid_cap = client.post(
        "/api/admin/rooms",
        json={
            "name": "C-101",
            "block_id": block.id,
            "floor": 1,
            "room_type": RoomType.CLASSROOM.value,
            "capacity": 0,
        },
        headers=admin_headers,
    )
    assert invalid_cap.status_code == 400

    # 2. Validation: LAB requires department
    lab_missing_dept = client.post(
        "/api/admin/rooms",
        json={
            "name": "ISE-LAB-01",
            "block_id": block.id,
            "floor": 1,
            "room_type": RoomType.LAB.value,
            "capacity": 40,
            "department_id": None,
        },
        headers=admin_headers,
    )
    assert lab_missing_dept.status_code == 400
    assert "Department is required for LAB" in lab_missing_dept.text

    # 3. Create LAB with department & facilities
    lab_resp = client.post(
        "/api/admin/rooms",
        json={
            "name": "ISE-LAB-01",
            "block_id": block.id,
            "floor": 1,
            "room_type": RoomType.LAB.value,
            "capacity": 40,
            "department_id": dept.id,
            "facility_ids": [fac1.id, fac2.id],
        },
        headers=admin_headers,
    )
    assert lab_resp.status_code == 201
    lab_id = lab_resp.json()["id"]
    assert len(lab_resp.json()["facilities"]) == 2

    # 4. Create other room types (CLASSROOM, EXAM_HALL, SEMINAR_HALL)
    types_to_test = [
        (RoomType.CLASSROOM, "C-201", 60),
        (RoomType.EXAM_HALL, "EXAM-MAIN", 200),
        (RoomType.SEMINAR_HALL, "AUDITORIUM", 300),
    ]
    for rtype, rname, cap in types_to_test:
        cr_resp = client.post(
            "/api/admin/rooms",
            json={
                "name": rname,
                "block_id": block.id,
                "floor": 2,
                "room_type": rtype.value,
                "capacity": cap,
            },
            headers=admin_headers,
        )
        assert cr_resp.status_code == 201

    # 5. List rooms with filters
    list_resp = client.get(
        f"/api/admin/rooms?block_id={block.id}&room_type=LAB",
        headers=admin_headers,
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1
    assert list_resp.json()["items"][0]["name"] == "ISE-LAB-01"

    # 6. Status change endpoint: Set to MAINTENANCE with note
    maint_resp = client.patch(
        f"/api/admin/rooms/{lab_id}/status",
        json={
            "status": RoomStatus.MAINTENANCE.value,
            "maintenance_note": "Upgrading server racks and network switches",
        },
        headers=admin_headers,
    )
    assert maint_resp.status_code == 200
    assert maint_resp.json()["status"] == RoomStatus.MAINTENANCE.value
    assert maint_resp.json()["maintenance_note"] == "Upgrading server racks and network switches"

    # 7. Status change back to ACTIVE
    active_resp = client.post(
        f"/api/admin/rooms/{lab_id}/status",
        json={"status": RoomStatus.ACTIVE.value},
        headers=admin_headers,
    )
    assert active_resp.status_code == 200
    assert active_resp.json()["status"] == RoomStatus.ACTIVE.value
    assert active_resp.json()["maintenance_note"] is None

    # 8. Delete room
    del_resp = client.delete(f"/api/admin/rooms/{lab_id}", headers=admin_headers)
    assert del_resp.status_code == 200


# -------------------------------------------------------------
# 7. Time Slots CRUD
# -------------------------------------------------------------

def test_time_slots_crud(client: TestClient, seed_users):
    admin_headers = get_auth_headers(seed_users["admin"])

    # 1. Validation: start_time >= end_time -> 400
    invalid_times = client.post(
        "/api/admin/time-slots",
        json={
            "label": "Invalid Slot",
            "start_time": "11:00:00",
            "end_time": "10:00:00",
            "order": 1,
        },
        headers=admin_headers,
    )
    assert invalid_times.status_code == 400

    # 2. Create valid time slot
    valid_resp = client.post(
        "/api/admin/time-slots",
        json={
            "label": "Morning Session 1",
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "order": 1,
        },
        headers=admin_headers,
    )
    assert valid_resp.status_code == 201
    slot_id = valid_resp.json()["id"]

    # 3. List time slots
    list_resp = client.get("/api/admin/time-slots?search=Morning", headers=admin_headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. Update time slot
    update_resp = client.patch(
        f"/api/admin/time-slots/{slot_id}",
        json={"label": "Period 1 (09:00 - 10:00)"},
        headers=admin_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["label"] == "Period 1 (09:00 - 10:00)"

    # 5. Delete time slot
    del_resp = client.delete(f"/api/admin/time-slots/{slot_id}", headers=admin_headers)
    assert del_resp.status_code == 200


# -------------------------------------------------------------
# 8. Timetable Entries & CSV Import
# -------------------------------------------------------------

def test_timetable_crud_and_csv_import(client: TestClient, seed_users, db_session: Session):
    admin_headers = get_auth_headers(seed_users["admin"])

    # Setup prerequisites
    block = Block(name="Main Campus Wing")
    dept = Department(name="Mechanical Eng", code="MECH", hod_approval_required=False)
    db_session.add_all([block, dept])
    db_session.commit()

    room = Room(name="MECH-101", block_id=block.id, floor=1, room_type=RoomType.CLASSROOM, capacity=50)
    slot1 = TimeSlot(label="Period 1", start_time=time(9, 0), end_time=time(10, 0), order=1)
    slot2 = TimeSlot(label="Period 2", start_time=time(10, 0), end_time=time(11, 0), order=2)
    db_session.add_all([room, slot1, slot2])
    db_session.commit()

    # 1. Validation: invalid day_of_week (> 6) -> 400
    inv_day = client.post(
        "/api/admin/timetable",
        json={
            "room_id": room.id,
            "day_of_week": 7,
            "slot_id": slot1.id,
            "department_id": dept.id,
            "subject": "Thermodynamics",
            "faculty_name": "Prof. Carnot",
        },
        headers=admin_headers,
    )
    assert inv_day.status_code == 400

    # 2. Create valid entry
    cr_resp = client.post(
        "/api/admin/timetable",
        json={
            "room_id": room.id,
            "day_of_week": 0,  # Monday
            "slot_id": slot1.id,
            "department_id": dept.id,
            "subject": "Thermodynamics",
            "faculty_name": "Prof. Carnot",
        },
        headers=admin_headers,
    )
    assert cr_resp.status_code == 201
    entry_id = cr_resp.json()["id"]

    # 3. Duplicate slot conflict -> 409
    dup_resp = client.post(
        "/api/admin/timetable",
        json={
            "room_id": room.id,
            "day_of_week": 0,
            "slot_id": slot1.id,
            "department_id": dept.id,
            "subject": "Fluid Mechanics",
            "faculty_name": "Prof. Euler",
        },
        headers=admin_headers,
    )
    assert dup_resp.status_code == 409

    # 4. List timetable entries
    list_resp = client.get(f"/api/admin/timetable?room_id={room.id}&day_of_week=0", headers=admin_headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 5. CSV Import test
    csv_content = f"""room,day,slot,department,subject,faculty
MECH-101,Tuesday,2,MECH,Fluid Dynamics,Prof. Euler
MECH-101,Wednesday,1,MECH,Heat Transfer,Prof. Fourier
MECH-101,0,1,MECH,Conflicting Class,Prof. Kelvin
"""
    files = {"file": ("timetable.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    import_resp = client.post("/api/admin/timetable/import-csv", files=files, headers=admin_headers)
    assert import_resp.status_code == 200
    import_data = import_resp.json()
    assert import_data["total_rows"] == 3
    assert import_data["imported"] == 2
    assert import_data["failed"] == 1  # 1 conflict on Monday slot 1
    assert len(import_data["errors"]) == 1

    # Clean up single entry
    del_resp = client.delete(f"/api/admin/timetable/{entry_id}", headers=admin_headers)
    assert del_resp.status_code == 200


# -------------------------------------------------------------
# 9. Booking History & CSV Export
# -------------------------------------------------------------

def test_booking_history_and_csv_export(client: TestClient, seed_users, db_session: Session):
    admin_headers = get_auth_headers(seed_users["admin"])

    # Setup room and slots
    block = Block(name="Main Tech Tower")
    dept = Department(name="Civil Eng", code="CIVIL", hod_approval_required=False)
    db_session.add_all([block, dept])
    db_session.commit()

    room = Room(name="CIVIL-AUD", block_id=block.id, floor=1, room_type=RoomType.SEMINAR_HALL, capacity=100)
    slot = TimeSlot(label="Afternoon 1", start_time=time(14, 0), end_time=time(15, 0), order=4)
    db_session.add_all([room, slot])
    db_session.commit()

    # Seed sample booking
    booking = Booking(
        reference="BK-2026-TEST",
        room_id=room.id,
        date=date(2026, 10, 15),
        slot_id=slot.id,
        purpose="Annual Structural Design Symposium",
        expected_strength=80,
        required_facilities=[],
        status=BookingStatus.APPROVED,
        requires_hod_approval=False,
        requester_type=RequesterType.FACULTY,
        name="Dr. Roebling",
        department_id=dept.id,
        phone="+1-555-4321",
        email="roebling@college.edu",
    )
    db_session.add(booking)
    db_session.commit()

    # 1. Filter bookings
    res = client.get(
        f"/api/admin/bookings?status={BookingStatus.APPROVED.value}&requester=Roebling",
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["reference"] == "BK-2026-TEST"

    # 2. Export CSV
    export_res = client.get(
        f"/api/admin/bookings/export-csv?status={BookingStatus.APPROVED.value}",
        headers=admin_headers,
    )
    assert export_res.status_code == 200
    assert "text/csv" in export_res.headers["content-type"]
    csv_text = export_res.text
    assert "BK-2026-TEST" in csv_text
    assert "Dr. Roebling" in csv_text
    assert "Annual Structural Design Symposium" in csv_text


# -------------------------------------------------------------
# 10. Audit Log Viewer Endpoint
# -------------------------------------------------------------

def test_audit_log_viewer(client: TestClient, seed_users):
    admin_headers = get_auth_headers(seed_users["admin"])

    # Create a department to trigger an audit record
    client.post(
        "/api/admin/departments",
        json={"name": "Audit Test Dept", "code": "ATD"},
        headers=admin_headers,
    )

    # View audit logs
    res = client.get("/api/admin/audit-logs?action=DEPARTMENT_CREATED", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert any(log["action"] == "DEPARTMENT_CREATED" for log in data["items"])


# -------------------------------------------------------------
# 11. Admin Overview & Room CSV Import
# -------------------------------------------------------------

def test_admin_overview_endpoint(client: TestClient, seed_users):
    admin_headers = get_auth_headers(seed_users["admin"])
    res = client.get("/api/admin/overview", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_rooms" in data
    assert "in_maintenance" in data
    assert "bookings_today" in data
    assert "pending_bookings" in data
    assert "utilization_rate" in data
    assert "bookings_per_day" in data
    assert len(data["bookings_per_day"]) == 7
    assert "room_type_usage" in data
    assert len(data["room_type_usage"]) >= 4


def test_rooms_csv_import(client: TestClient, seed_users):
    admin_headers = get_auth_headers(seed_users["admin"])

    # Create block and dept first
    b_res = client.post("/api/admin/blocks", json={"name": "CSV Test Block"}, headers=admin_headers)
    assert b_res.status_code in [201, 409]
    d_res = client.post("/api/admin/departments", json={"name": "CSV Test Dept", "code": "CTD"}, headers=admin_headers)
    assert d_res.status_code in [201, 409]

    csv_data = (
        "name,block,floor,room_type,capacity,department,facilities,status\n"
        "CSV-101,CSV Test Block,1,CLASSROOM,60,,Projector;AC,ACTIVE\n"
        "CSV-LAB-1,CSV Test Block,2,LAB,35,CTD,PCs;AC;Internet,ACTIVE\n"
    )

    import io
    file_payload = {"file": ("rooms.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    res = client.post("/api/admin/rooms/import-csv", files=file_payload, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_rows"] == 2
    assert data["imported"] == 2
    assert len(data["errors"]) == 0


