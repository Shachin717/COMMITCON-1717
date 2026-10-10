from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.audit_log import AuditLog
from app.models.block import Block, BlockCoordinator
from app.models.department import Department
from app.models.enums import UserRole
from app.models.otp import OtpCode
from app.models.user import User


@pytest.fixture
def matrix_setup(db_session: Session):
    password_hash = hash_password("Secret123!")

    dept = Department(name="Computer Science", code="CS", hod_approval_required=True)
    block = Block(name="Main Block", description="Test Block")
    db_session.add_all([dept, block])
    db_session.flush()

    admin = User(
        name="Admin User",
        email="admin@test.edu",
        password_hash=password_hash,
        role=UserRole.ADMIN,
        is_active=True,
    )
    coord = User(
        name="Coord User",
        email="coord@test.edu",
        password_hash=password_hash,
        role=UserRole.COORDINATOR,
        is_active=True,
    )
    faculty = User(
        name="Faculty User",
        email="faculty@test.edu",
        password_hash=password_hash,
        role=UserRole.FACULTY,
        is_active=True,
    )
    hod = User(
        name="HOD User",
        email="hod@test.edu",
        password_hash=password_hash,
        role=UserRole.HOD,
        department_id=dept.id,
        is_active=True,
    )

    db_session.add_all([admin, coord, faculty, hod])
    db_session.flush()

    # Assign block to coordinator
    coord_block = BlockCoordinator(user_id=coord.id, block_id=block.id)
    db_session.add(coord_block)
    db_session.commit()

    return {
        "admin": admin,
        "coordinator": coord,
        "faculty": faculty,
        "hod": hod,
        "dept": dept,
        "block": block,
    }


# ====================================================================
# 1. 4x4 Role x Portal Login Matrix
# ====================================================================
PORTALS = [
    ("admin", "/api/auth/admin/login", UserRole.ADMIN),
    ("coordinator", "/api/auth/coordinator/login", UserRole.COORDINATOR),
    ("faculty", "/api/auth/faculty/login", UserRole.FACULTY),
    ("hod", "/api/auth/hod/login", UserRole.HOD),
]

ROLES = ["admin", "coordinator", "faculty", "hod"]


@pytest.mark.parametrize("role_name", ROLES)
@pytest.mark.parametrize("portal_name,portal_endpoint,expected_role", PORTALS)
def test_role_x_portal_login_matrix(
    client: TestClient,
    db_session: Session,
    matrix_setup,
    role_name,
    portal_name,
    portal_endpoint,
    expected_role,
):
    user = matrix_setup[role_name]
    res = client.post(
        portal_endpoint,
        json={"email": user.email, "password": "Secret123!"},
    )

    if user.role == expected_role:
        # Matching portal: 200 OK
        assert res.status_code == 200, f"Expected 200 for {role_name} on {portal_name}, got {res.text}"
        data = res.json()
        assert data["user"]["role"] == expected_role.value
        assert "access_token" in data
        assert "access_token" in res.cookies
    else:
        # Wrong portal: 401 Unauthorized with generic message
        assert res.status_code == 401, f"Expected 401 for {role_name} on {portal_name}, got {res.status_code}"
        assert res.json()["detail"] == "Invalid credentials"

        # Check AuditLog: must record 'wrong portal login attempt' and must NOT reveal real role
        audit = (
            db_session.query(AuditLog)
            .filter(AuditLog.actor_id == user.id)
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert audit is not None
        assert audit.action == "wrong portal login attempt"
        assert audit.meta.get("portal") == portal_name
        # Ensure actual role is not leaked in audit meta
        assert "role" not in audit.meta or audit.meta.get("role") != user.role.value


# ====================================================================
# 2. Disabled shared /staff/login endpoint
# ====================================================================
def test_shared_staff_login_is_disabled(client: TestClient, matrix_setup):
    for role_name in ROLES:
        user = matrix_setup[role_name]
        res = client.post(
            "/api/auth/staff/login",
            json={"email": user.email, "password": "Secret123!"},
        )
        assert res.status_code == 410, f"Expected 410 for disabled endpoint, got {res.status_code}"


# ====================================================================
# 3. Role x Endpoint-Group Matrix (Authorization)
# ====================================================================
ENDPOINT_GROUPS = [
    ("admin", "/api/admin/overview", UserRole.ADMIN),
    ("coordinator", "/api/coordinator/blocks", UserRole.COORDINATOR),
    ("faculty", "/api/faculty/bookings", UserRole.FACULTY),
    ("hod", "/api/hod/summary", UserRole.HOD),
]


@pytest.mark.parametrize("role_name", ROLES)
@pytest.mark.parametrize("group_name,endpoint,allowed_role", ENDPOINT_GROUPS)
def test_role_x_endpoint_group_matrix(
    client: TestClient,
    matrix_setup,
    role_name,
    group_name,
    endpoint,
    allowed_role,
):
    user = matrix_setup[role_name]
    token = create_access_token(
        subject=user.id,
        extra_claims={"email": user.email, "role": user.role.value},
    )
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get(endpoint, headers=headers)

    if user.role == allowed_role:
        assert res.status_code == 200, (
            f"Expected 200 for role {role_name} on {group_name} ({endpoint}), got {res.status_code}: {res.text}"
        )
    else:
        assert res.status_code == 403, (
            f"Expected 403 Forbidden for role {role_name} on {group_name} ({endpoint}), got {res.status_code}"
        )


# ====================================================================
# 4. Per-Portal Forgot-Password & OTP Isolation
# ====================================================================
def test_per_portal_forgot_password_isolation(client: TestClient, db_session: Session, matrix_setup):
    coord_user = matrix_setup["coordinator"]

    # 1. Requesting OTP for a coordinator account from the ADMIN portal
    with patch("app.api.v1.endpoints.auth.send_password_reset_otp_email") as mock_email:
        res = client.post(
            "/api/auth/forgot-password",
            json={"email": coord_user.email, "portal": "admin"},
        )
        assert res.status_code == 200
        assert "password reset code has been sent" in res.json()["message"]
        # Email must NOT be dispatched for wrong portal
        assert mock_email.call_count == 0

        # No OTP record created with admin purpose
        otp_admin = (
            db_session.query(OtpCode)
            .filter(OtpCode.email == coord_user.email, OtpCode.purpose == "password_reset:admin")
            .first()
        )
        assert otp_admin is None

    # 2. Requesting OTP for a coordinator account from the COORDINATOR portal
    with patch("app.api.v1.endpoints.auth.send_password_reset_otp_email") as mock_email:
        res = client.post(
            "/api/auth/forgot-password",
            json={"email": coord_user.email, "portal": "coordinator"},
        )
        assert res.status_code == 200
        assert mock_email.call_count == 1
        sent_otp = mock_email.call_args[1]["otp_code"]

        # OTP record created with coordinator purpose
        otp_coord = (
            db_session.query(OtpCode)
            .filter(OtpCode.email == coord_user.email, OtpCode.purpose == "password_reset:coordinator")
            .first()
        )
        assert otp_coord is not None

    # 3. Trying to verify coordinator OTP from ADMIN portal -> 400 Bad Request
    v_admin = client.post(
        "/api/auth/verify-otp",
        json={"email": coord_user.email, "otp": sent_otp, "portal": "admin"},
    )
    assert v_admin.status_code == 400

    # 4. Verifying coordinator OTP from COORDINATOR portal -> 200 OK
    v_coord = client.post(
        "/api/auth/verify-otp",
        json={"email": coord_user.email, "otp": sent_otp, "portal": "coordinator"},
    )
    assert v_coord.status_code == 200
    reset_token = v_coord.json()["reset_token"]

    # 5. Trying to reset password using that token on ADMIN portal -> 400
    r_admin = client.post(
        "/api/auth/reset-password",
        json={
            "email": coord_user.email,
            "reset_token": reset_token,
            "new_password": "NewCoordPassword123!",
            "portal": "admin",
        },
    )
    assert r_admin.status_code == 400

    # 6. Resetting password using that token on COORDINATOR portal -> 200
    r_coord = client.post(
        "/api/auth/reset-password",
        json={
            "email": coord_user.email,
            "reset_token": reset_token,
            "new_password": "NewCoordPassword123!",
            "portal": "coordinator",
        },
    )
    assert r_coord.status_code == 200

    # 7. Login with new password on coordinator portal succeeds
    login_res = client.post(
        "/api/auth/coordinator/login",
        json={"email": coord_user.email, "password": "NewCoordPassword123!"},
    )
    assert login_res.status_code == 200


# ====================================================================
# 5. Immediate Role Change / Account Deactivation Invalidation
# ====================================================================
def test_immediate_role_change_invalidation(client: TestClient, db_session: Session, matrix_setup):
    coord_user = matrix_setup["coordinator"]
    token = create_access_token(
        subject=coord_user.id,
        extra_claims={"email": coord_user.email, "role": coord_user.role.value},
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Initial request works
    res1 = client.get("/api/coordinator/blocks", headers=headers)
    assert res1.status_code == 200

    # Change user's role in DB to FACULTY
    coord_user.role = UserRole.FACULTY
    db_session.commit()

    # Next request with old token must be immediately rejected (401)
    res2 = client.get("/api/coordinator/blocks", headers=headers)
    assert res2.status_code == 401
    assert "role has changed" in res2.json()["detail"].lower()


def test_immediate_deactivation_invalidation(client: TestClient, db_session: Session, matrix_setup):
    admin_user = matrix_setup["admin"]
    token = create_access_token(
        subject=admin_user.id,
        extra_claims={"email": admin_user.email, "role": admin_user.role.value},
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Initial request works
    res1 = client.get("/api/admin/overview", headers=headers)
    assert res1.status_code == 200

    # Deactivate admin account
    admin_user.is_active = False
    db_session.commit()

    # Next request must be immediately rejected (401)
    res2 = client.get("/api/admin/overview", headers=headers)
    assert res2.status_code == 401
    assert "inactive" in res2.json()["detail"].lower()

