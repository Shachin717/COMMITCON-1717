import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.security import create_access_token
from app.models.department import Department
from app.models.user import User
from app.models.classroom import Classroom
from app.models.building import Building
from app.models.approval_policy import ApprovalPolicy

@pytest.fixture
def setup_departments(db_session: Session):
    d1 = Department(name="CSE", code="CSE")
    d2 = Department(name="ECE", code="ECE")
    db_session.add_all([d1, d2])
    db_session.commit()
    return [d1, d2]

@pytest.fixture
def setup_classrooms(db_session: Session):
    b = Building(name="Main", location="Campus")
    db_session.add(b)
    db_session.commit()
    
    r1 = Classroom(name="101", building_id=b.id, capacity=40, room_type="CLASSROOM", is_active=True)
    db_session.add(r1)
    db_session.commit()
    return [r1]

@pytest.fixture(autouse=True)
def setup_approval_policies(db_session: Session):
    db_session.add_all([
        ApprovalPolicy(purpose="REGULAR_CLASS", requires_hod_approval=False),
        ApprovalPolicy(purpose="EXAMINATION", requires_hod_approval=True),
        ApprovalPolicy(purpose="MCQ_TEST", requires_hod_approval=True),
        ApprovalPolicy(purpose="SEMINAR", requires_hod_approval=False),
        ApprovalPolicy(purpose="WORKSHOP", requires_hod_approval=False),
        ApprovalPolicy(purpose="EVENT", requires_hod_approval=False),
        ApprovalPolicy(purpose="OTHER", requires_hod_approval=False),
    ])
    db_session.commit()

def get_admin_headers():
    token = create_access_token({"sub": "admin", "role": "ADMIN", "user_id": 1, "email": "admin@test.com", "is_admin": True})
    return {"Authorization": f"Bearer {token}"}

def get_hod_headers(user_id: int, department_id: int):
    token = create_access_token({"sub": "hod_user", "role": "HOD", "user_id": user_id, "email": "hod@test.com", "department_id": department_id})
    return {"Authorization": f"Bearer {token}"}

def test_create_hod_account(client: TestClient, db_session: Session, setup_departments):
    dept_id = setup_departments[0].id
    headers = get_admin_headers()
    
    response = client.post(
        "/api/v1/hod/accounts",
        headers=headers,
        json={
            "username": "new_hod",
            "email": "new_hod@test.com",
            "password": "password123",
            "department_id": dept_id
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "HOD"
    assert data["department_id"] == dept_id

def test_hod_login(client: TestClient, db_session: Session, setup_departments):
    dept_id = setup_departments[0].id
    
    # Create HOD first
    from app.services.hod_service import HODService
    from app.schemas.user import HODCreate
    service = HODService(db_session)
    hod = service.create_hod(HODCreate(username="hod_login_test", email="hodlogin@test.com", password="password123", department_id=dept_id))
    
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "hod_login_test", "password": "password123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "HOD"

def test_booking_requires_approval(client: TestClient, db_session: Session, setup_classrooms, setup_departments):
    room = setup_classrooms[0]
    dept_id = setup_departments[0].id
    
    now = datetime.now(timezone.utc)
    start = (now + timedelta(days=1)).isoformat()
    end = (now + timedelta(days=1, hours=2)).isoformat()
    
    headers = get_admin_headers()
    
    response = client.post(
        "/api/v1/bookings",
        headers=headers,
        json={
            "room_id": room.id,
            "title": "Exam Booking",
            "start_datetime": start,
            "end_datetime": end,
            "department_id": dept_id,
            "purpose": "EXAMINATION"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "PENDING_HOD_APPROVAL"
    assert data["purpose"] == "EXAMINATION"

def test_booking_no_approval(client: TestClient, db_session: Session, setup_classrooms, setup_departments):
    room = setup_classrooms[0]
    dept_id = setup_departments[0].id
    
    now = datetime.now(timezone.utc)
    start = (now + timedelta(days=2)).isoformat()
    end = (now + timedelta(days=2, hours=2)).isoformat()
    
    headers = get_admin_headers()
    
    response = client.post(
        "/api/v1/bookings",
        headers=headers,
        json={
            "room_id": room.id,
            "title": "Regular Class Booking",
            "start_datetime": start,
            "end_datetime": end,
            "department_id": dept_id,
            "purpose": "REGULAR_CLASS"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "CONFIRMED"

def test_hod_approve_request(client: TestClient, db_session: Session, setup_classrooms, setup_departments):
    room = setup_classrooms[0]
    dept_id = setup_departments[0].id
    
    # Setup HOD
    from app.services.hod_service import HODService
    from app.schemas.user import HODCreate
    service = HODService(db_session)
    hod = service.create_hod(HODCreate(username="hod_approve_test", email="hod_approve@test.com", password="password123", department_id=dept_id))
    
    now = datetime.now(timezone.utc)
    start = (now + timedelta(days=3)).isoformat()
    end = (now + timedelta(days=3, hours=2)).isoformat()
    
    # Create booking
    booking_resp = client.post(
        "/api/v1/bookings",
        headers=get_admin_headers(),
        json={
            "room_id": room.id,
            "title": "Exam Booking to Approve",
            "start_datetime": start,
            "end_datetime": end,
            "department_id": dept_id,
            "purpose": "EXAMINATION"
        }
    )
    booking_id = booking_resp.json()["id"]
    
    # HOD approves
    headers = get_hod_headers(hod.id, dept_id)
    resp = client.post(
        f"/api/v1/hod/requests/{booking_id}/decide",
        headers=headers,
        json={
            "decision": "APPROVED",
            "remarks": "Looks good"
        }
    )
    assert resp.status_code == 200
    assert resp.json()["decision"] == "APPROVED"
    
    # Check booking status
    check = client.get(f"/api/v1/bookings/{booking_id}")
    assert check.json()["status"] == "CONFIRMED"

def test_hod_reject_request(client: TestClient, db_session: Session, setup_classrooms, setup_departments):
    room = setup_classrooms[0]
    dept_id = setup_departments[0].id
    
    # Setup HOD
    from app.services.hod_service import HODService
    from app.schemas.user import HODCreate
    service = HODService(db_session)
    hod = service.create_hod(HODCreate(username="hod_reject_test", email="hod_reject@test.com", password="password123", department_id=dept_id))
    
    now = datetime.now(timezone.utc)
    start = (now + timedelta(days=4)).isoformat()
    end = (now + timedelta(days=4, hours=2)).isoformat()
    
    # Create booking
    booking_resp = client.post(
        "/api/v1/bookings",
        headers=get_admin_headers(),
        json={
            "room_id": room.id,
            "title": "Exam Booking to Reject",
            "start_datetime": start,
            "end_datetime": end,
            "department_id": dept_id,
            "purpose": "EXAMINATION"
        }
    )
    booking_id = booking_resp.json()["id"]
    
    # HOD rejects
    headers = get_hod_headers(hod.id, dept_id)
    resp = client.post(
        f"/api/v1/hod/requests/{booking_id}/decide",
        headers=headers,
        json={
            "decision": "REJECTED",
            "remarks": "Not allowed"
        }
    )
    assert resp.status_code == 200
    
    # Check booking status
    check = client.get(f"/api/v1/bookings/{booking_id}")
    assert check.json()["status"] == "REJECTED"
    assert check.json()["rejection_reason"] == "Not allowed"

def test_hod_cannot_access_other_department(client: TestClient, db_session: Session, setup_classrooms, setup_departments):
    room = setup_classrooms[0]
    dept1_id = setup_departments[0].id
    dept2_id = setup_departments[1].id
    
    # Setup HOD for dept2
    from app.services.hod_service import HODService
    from app.schemas.user import HODCreate
    service = HODService(db_session)
    hod = service.create_hod(HODCreate(username="hod_other_dept", email="hod_other@test.com", password="password123", department_id=dept2_id))
    
    now = datetime.now(timezone.utc)
    start = (now + timedelta(days=5)).isoformat()
    end = (now + timedelta(days=5, hours=2)).isoformat()
    
    # Create booking for dept1
    booking_resp = client.post(
        "/api/v1/bookings",
        headers=get_admin_headers(),
        json={
            "room_id": room.id,
            "title": "Dept1 Exam",
            "start_datetime": start,
            "end_datetime": end,
            "department_id": dept1_id,
            "purpose": "EXAMINATION"
        }
    )
    booking_id = booking_resp.json()["id"]
    
    # HOD for dept2 tries to approve dept1's booking
    headers = get_hod_headers(hod.id, dept2_id)
    resp = client.post(
        f"/api/v1/hod/requests/{booking_id}/decide",
        headers=headers,
        json={
            "decision": "APPROVED",
            "remarks": "Ok"
        }
    )
    assert resp.status_code == 403

def test_approval_policy_list(client: TestClient, db_session: Session):
    headers = get_admin_headers()
    response = client.get("/api/v1/approval-policies", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 7

def test_concurrent_approval_safety(client: TestClient, db_session: Session, setup_classrooms, setup_departments):
    room = setup_classrooms[0]
    dept_id = setup_departments[0].id
    
    # Setup HOD
    from app.services.hod_service import HODService
    from app.schemas.user import HODCreate
    service = HODService(db_session)
    hod = service.create_hod(HODCreate(username="hod_concurrent_test", email="hod_conc@test.com", password="password123", department_id=dept_id))
    
    now = datetime.now(timezone.utc)
    start = (now + timedelta(days=6)).isoformat()
    end = (now + timedelta(days=6, hours=2)).isoformat()
    
    # Create booking
    booking_resp = client.post(
        "/api/v1/bookings",
        headers=get_admin_headers(),
        json={
            "room_id": room.id,
            "title": "Exam Booking Double Approve",
            "start_datetime": start,
            "end_datetime": end,
            "department_id": dept_id,
            "purpose": "EXAMINATION"
        }
    )
    booking_id = booking_resp.json()["id"]
    
    # HOD approves first time
    headers = get_hod_headers(hod.id, dept_id)
    resp1 = client.post(
        f"/api/v1/hod/requests/{booking_id}/decide",
        headers=headers,
        json={
            "decision": "APPROVED"
        }
    )
    assert resp1.status_code == 200
    
    # HOD tries to approve again
    resp2 = client.post(
        f"/api/v1/hod/requests/{booking_id}/decide",
        headers=headers,
        json={
            "decision": "APPROVED"
        }
    )
    assert resp2.status_code == 422
