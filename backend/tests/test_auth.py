from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.rate_limit import limiter
from app.core.security import hash_token
from app.main import app
from app.models.audit_log import AuditLog
from app.models.enums import UserRole
from app.models.otp import OtpCode
from app.models.user import User


# Add temporary test route to test require_roles helper
@app.get("/api/test/admin-only")
def admin_only_endpoint(user: User = Depends(require_roles(UserRole.ADMIN))):
    return {"message": "Admin access granted", "user_id": user.id}


@app.get("/api/test/coordinator-or-faculty")
def coordinator_faculty_endpoint(
    user: User = Depends(require_roles(UserRole.COORDINATOR, UserRole.FACULTY))
):
    return {"message": "Staff access granted", "role": user.role.value}


def test_role_logins_success(client: TestClient, seed_users, db_session: Session):
    role_portal_map = {
        "admin": "/api/auth/admin/login",
        "coordinator": "/api/auth/coordinator/login",
        "faculty": "/api/auth/faculty/login",
        "hod": "/api/auth/hod/login",
    }
    for role_name, endpoint in role_portal_map.items():
        user = seed_users[role_name]
        response = client.post(
            endpoint,
            json={"email": user.email, "password": "Secret123!"},
        )
        assert response.status_code == 200, f"Login failed for {role_name} on {endpoint}: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == user.email
        assert data["user"]["role"] == user.role.value

        # Check cookies
        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies


def test_staff_login_disabled(client: TestClient, seed_users):
    """Old shared /staff/login endpoint must be disabled."""
    response = client.post(
        "/api/auth/staff/login",
        json={"email": "admin@college.edu", "password": "Secret123!"},
    )
    assert response.status_code == 410


def test_wrong_portal_cross_logins(client: TestClient, seed_users):
    """Ensure wrong portal logins return 401 with generic Invalid credentials."""
    portals = [
        "/api/auth/admin/login",
        "/api/auth/coordinator/login",
        "/api/auth/faculty/login",
        "/api/auth/hod/login",
    ]
    for portal in portals:
        # HOD trying other portals
        if portal != "/api/auth/hod/login":
            resp = client.post(
                portal,
                json={"email": seed_users["hod"].email, "password": "Secret123!"},
            )
            assert resp.status_code == 401
            assert resp.json()["detail"] == "Invalid credentials"

        # Admin trying other portals
        if portal != "/api/auth/admin/login":
            resp = client.post(
                portal,
                json={"email": seed_users["admin"].email, "password": "Secret123!"},
            )
            assert resp.status_code == 401
            assert resp.json()["detail"] == "Invalid credentials"


def test_login_invalid_password(client: TestClient, seed_users):
    response = client.post(
        "/api/auth/admin/login",
        json={"email": "admin@college.edu", "password": "WrongPassword!"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_inactive_user(client: TestClient, seed_users):
    response = client.post(
        "/api/auth/faculty/login",
        json={"email": "inactive@college.edu", "password": "Secret123!"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_nonexistent_user(client: TestClient):
    response = client.post(
        "/api/auth/admin/login",
        json={"email": "ghost@college.edu", "password": "Secret123!"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_get_current_user_me(client: TestClient, seed_users):
    # Unauthenticated
    unauth_resp = client.get("/api/auth/me")
    assert unauth_resp.status_code == 401

    # Authenticate via admin login
    login_resp = client.post(
        "/api/auth/admin/login",
        json={"email": "admin@college.edu", "password": "Secret123!"},
    )
    assert login_resp.status_code == 200

    # Me with cookie
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "admin@college.edu"


def test_role_based_dependency_require_roles(client: TestClient, seed_users):
    # Log in as coordinator
    client.post(
        "/api/auth/coordinator/login",
        json={"email": "coordinator@college.edu", "password": "Secret123!"},
    )

    # Coordinator accessing admin-only endpoint should be forbidden (403)
    forbidden_resp = client.get("/api/test/admin-only")
    assert forbidden_resp.status_code == 403
    assert forbidden_resp.json()["detail"] == "Access forbidden: insufficient permissions"

    # Coordinator accessing coordinator-or-faculty endpoint should succeed (200)
    allowed_resp = client.get("/api/test/coordinator-or-faculty")
    assert allowed_resp.status_code == 200
    assert allowed_resp.json()["role"] == UserRole.COORDINATOR.value


def test_refresh_token_flow(client: TestClient, seed_users):
    login_resp = client.post(
        "/api/auth/faculty/login",
        json={"email": "faculty@college.edu", "password": "Secret123!"},
    )
    assert login_resp.status_code == 200
    initial_access_token = login_resp.json()["access_token"]

    # Call refresh endpoint with cookies
    refresh_resp = client.post("/api/auth/refresh")
    assert refresh_resp.status_code == 200
    refreshed_data = refresh_resp.json()
    assert "access_token" in refreshed_data
    assert refreshed_data["user"]["email"] == "faculty@college.edu"
    assert "access_token" in refresh_resp.cookies


def test_refresh_token_invalid_or_missing(client: TestClient):
    client.cookies.clear()
    resp = client.post("/api/auth/refresh")
    assert resp.status_code == 401

    client.cookies.set("refresh_token", "invalid.jwt.token")
    resp_invalid = client.post("/api/auth/refresh")
    assert resp_invalid.status_code == 401


def test_logout(client: TestClient, seed_users):
    client.post(
        "/api/auth/admin/login",
        json={"email": "admin@college.edu", "password": "Secret123!"},
    )
    assert "access_token" in client.cookies

    logout_resp = client.post("/api/auth/logout")
    assert logout_resp.status_code == 200
    assert logout_resp.json()["message"] == "Logged out successfully"

    # Subsequent call to /me should fail
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 401


def test_forgot_password_nonexistent_email(client: TestClient, db_session: Session):
    response = client.post(
        "/api/auth/forgot-password",
        json={"email": "nonexistent@college.edu"},
    )
    # Never reveal whether the email exists
    assert response.status_code == 200
    assert "If your email is registered" in response.json()["message"]

    # Verify no OTP was generated
    otp_count = db_session.query(OtpCode).filter(OtpCode.email == "nonexistent@college.edu").count()
    assert otp_count == 0


def test_forgot_password_success_and_otp_hashed(client: TestClient, seed_users, db_session: Session):
    with patch("app.api.v1.endpoints.auth.send_password_reset_otp_email") as mock_email:
        mock_email.return_value = True

        response = client.post(
            "/api/auth/forgot-password",
            json={"email": "faculty@college.edu"},
        )
        assert response.status_code == 200
        assert mock_email.called

        sent_otp = mock_email.call_args[1]["otp_code"]
        assert len(sent_otp) == 6
        assert sent_otp.isdigit()

        # Check DB record
        otp_record = (
            db_session.query(OtpCode)
            .filter(OtpCode.email == "faculty@college.edu")
            .order_by(OtpCode.id.desc())
            .first()
        )
        assert otp_record is not None
        assert otp_record.used is False
        assert otp_record.attempts == 0
        # Code must be stored hashed, not plaintext!
        assert otp_record.code_hash != sent_otp
        assert otp_record.code_hash == hash_token(sent_otp)


def test_forgot_password_resend_cooldown(client: TestClient, seed_users, db_session: Session):
    with patch("app.api.v1.endpoints.auth.send_password_reset_otp_email") as mock_email:
        mock_email.return_value = True

        # First request succeeds
        resp1 = client.post(
            "/api/auth/forgot-password",
            json={"email": "faculty@college.edu"},
        )
        assert resp1.status_code == 200

        # Immediate second request hits 60-second cooldown (429)
        resp2 = client.post(
            "/api/auth/forgot-password",
            json={"email": "faculty@college.edu"},
        )
        assert resp2.status_code == 429
        assert "60 seconds" in resp2.json()["detail"]


def test_verify_otp_success_and_reset_token(client: TestClient, seed_users, db_session: Session):
    with patch("app.api.v1.endpoints.auth.send_password_reset_otp_email") as mock_email:
        mock_email.return_value = True
        client.post(
            "/api/auth/forgot-password",
            json={"email": "faculty@college.edu"},
        )
        sent_otp = mock_email.call_args[1]["otp_code"]

    verify_resp = client.post(
        "/api/auth/verify-otp",
        json={"email": "faculty@college.edu", "otp": sent_otp},
    )
    assert verify_resp.status_code == 200
    data = verify_resp.json()
    assert data["valid"] is True
    assert "reset_token" in data
    assert data["reset_token"] is not None


def test_verify_otp_invalid_code(client: TestClient, seed_users, db_session: Session):
    with patch("app.api.v1.endpoints.auth.send_password_reset_otp_email") as mock_email:
        mock_email.return_value = True
        client.post(
            "/api/auth/forgot-password",
            json={"email": "coordinator@college.edu"},
        )

    verify_resp = client.post(
        "/api/auth/verify-otp",
        json={"email": "coordinator@college.edu", "otp": "000000"},
    )
    assert verify_resp.status_code == 400
    assert verify_resp.json()["detail"] == "Invalid OTP code"

    # Verify attempts incremented
    otp_record = (
        db_session.query(OtpCode)
        .filter(OtpCode.email == "coordinator@college.edu")
        .order_by(OtpCode.id.desc())
        .first()
    )
    assert otp_record.attempts == 1


def test_verify_otp_attempt_limit_exceeded(client: TestClient, seed_users, db_session: Session):
    with patch("app.api.v1.endpoints.auth.send_password_reset_otp_email") as mock_email:
        mock_email.return_value = True
        client.post(
            "/api/auth/forgot-password",
            json={"email": "admin@college.edu"},
        )

    # Fail 5 times
    for _ in range(5):
        resp = client.post(
            "/api/auth/verify-otp",
            json={"email": "admin@college.edu", "otp": "999999"},
        )
        assert resp.status_code == 400

    # 6th attempt should trigger maximum attempts exceeded
    locked_resp = client.post(
        "/api/auth/verify-otp",
        json={"email": "admin@college.edu", "otp": "999999"},
    )
    assert locked_resp.status_code == 400
    assert "Maximum OTP verification attempts exceeded" in locked_resp.json()["detail"]


def test_verify_otp_expired(client: TestClient, seed_users, db_session: Session):
    with patch("app.api.v1.endpoints.auth.send_password_reset_otp_email") as mock_email:
        mock_email.return_value = True
        client.post(
            "/api/auth/forgot-password",
            json={"email": "hod@college.edu"},
        )
        sent_otp = mock_email.call_args[1]["otp_code"]

    # Manually expire the OTP in DB
    otp_record = (
        db_session.query(OtpCode)
        .filter(OtpCode.email == "hod@college.edu")
        .order_by(OtpCode.id.desc())
        .first()
    )
    otp_record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    resp = client.post(
        "/api/auth/verify-otp",
        json={"email": "hod@college.edu", "otp": sent_otp},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "OTP has expired"


def test_reset_password_flow_with_reset_token(client: TestClient, seed_users, db_session: Session):
    with patch("app.api.v1.endpoints.auth.send_password_reset_otp_email") as mock_email:
        mock_email.return_value = True
        client.post(
            "/api/auth/forgot-password",
            json={"email": "faculty@college.edu"},
        )
        sent_otp = mock_email.call_args[1]["otp_code"]

    verify_resp = client.post(
        "/api/auth/verify-otp",
        json={"email": "faculty@college.edu", "otp": sent_otp},
    )
    reset_token = verify_resp.json()["reset_token"]

    # Reset password
    reset_resp = client.post(
        "/api/auth/reset-password",
        json={
            "email": "faculty@college.edu",
            "reset_token": reset_token,
            "new_password": "NewSecretPassword99!",
        },
    )
    assert reset_resp.status_code == 200
    assert reset_resp.json()["message"] == "Password reset successfully"

    # Login with old password fails
    old_login = client.post(
        "/api/auth/faculty/login",
        json={"email": "faculty@college.edu", "password": "Secret123!"},
    )
    assert old_login.status_code == 401

    # Login with new password succeeds
    new_login = client.post(
        "/api/auth/faculty/login",
        json={"email": "faculty@college.edu", "password": "NewSecretPassword99!"},
    )
    assert new_login.status_code == 200

    # Ensure single use: cannot reuse the same reset_token
    reuse_resp = client.post(
        "/api/auth/reset-password",
        json={
            "email": "faculty@college.edu",
            "reset_token": reset_token,
            "new_password": "AnotherPassword123!",
        },
    )
    assert reuse_resp.status_code == 400


def test_reset_password_flow_direct_otp(client: TestClient, seed_users, db_session: Session):
    with patch("app.api.v1.endpoints.auth.send_password_reset_otp_email") as mock_email:
        mock_email.return_value = True
        client.post(
            "/api/auth/forgot-password",
            json={"email": "coordinator@college.edu"},
        )
        sent_otp = mock_email.call_args[1]["otp_code"]

    # Reset password directly using otp
    reset_resp = client.post(
        "/api/auth/reset-password",
        json={
            "email": "coordinator@college.edu",
            "otp": sent_otp,
            "new_password": "CoordinatorNewPass1!",
        },
    )
    assert reset_resp.status_code == 200

    # Login with new password
    login_resp = client.post(
        "/api/auth/coordinator/login",
        json={"email": "coordinator@college.edu", "password": "CoordinatorNewPass1!"},
    )
    assert login_resp.status_code == 200


def test_audit_log_entries_created(client: TestClient, seed_users, db_session: Session):
    # Perform various actions and assert audit entries
    client.post(
        "/api/auth/admin/login",
        json={"email": "admin@college.edu", "password": "Secret123!"},
    )
    client.post(
        "/api/auth/hod/login",
        json={"email": "hod@college.edu", "password": "Secret123!"},
    )
    client.post(
        "/api/auth/admin/login",
        json={"email": "admin@college.edu", "password": "BadPassword"},
    )
    client.post("/api/auth/logout")

    actions = [entry.action for entry in db_session.query(AuditLog).all()]
    assert "LOGIN_ADMIN" in actions
    assert "LOGIN_HOD" in actions
    assert "LOGIN_FAILED" in actions
    assert "LOGOUT" in actions


def test_rate_limiting_enforcement(client: TestClient, seed_users):
    # Temporarily enable rate limiter to verify SlowAPI rate limiting behavior
    limiter.enabled = True
    try:
        # Rapidly attempt logins beyond the 10/minute threshold
        responses = []
        for _ in range(12):
            resp = client.post(
                "/api/auth/admin/login",
                json={"email": "admin@college.edu", "password": "WrongPassword"},
            )
            responses.append(resp.status_code)

        # At least one request should receive HTTP 429 Too Many Requests
        assert 429 in responses
    finally:
        limiter.enabled = False

