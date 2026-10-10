from datetime import datetime, timedelta, timezone
import secrets
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    decode_token,
    generate_numeric_otp,
    hash_password,
    hash_token,
    verify_otp,
    verify_password,
)
from app.models.enums import UserRole
from app.models.otp import OtpCode
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    TokenResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
)
from app.schemas.user import UserResponse
from app.services.audit import log_audit
from app.services.email import send_password_reset_otp_email

router = APIRouter()


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_expired(dt: datetime) -> bool:
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt < now.replace(tzinfo=None)
    return dt < now


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> str:
    access_max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    refresh_max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    is_secure = settings.is_cookie_secure
    samesite = settings.COOKIE_SAMESITE.lower()
    csrf_token = secrets.token_hex(32)

    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=access_max_age,
        httponly=True,
        samesite=samesite,
        secure=is_secure,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=refresh_max_age,
        httponly=True,
        samesite=samesite,
        secure=is_secure,
        path="/",
    )
    # Double-submit CSRF token (accessible to frontend script)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        max_age=refresh_max_age,
        httponly=False,
        samesite=samesite,
        secure=is_secure,
        path="/",
    )
    return csrf_token


def _clear_auth_cookies(response: Response) -> None:
    is_secure = settings.is_cookie_secure
    samesite = settings.COOKIE_SAMESITE.lower()

    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        samesite=samesite,
        secure=is_secure,
    )
    response.delete_cookie(
        key="refresh_token",
        path="/",
        httponly=True,
        samesite=samesite,
        secure=is_secure,
    )
    response.delete_cookie(
        key="csrf_token",
        path="/",
        httponly=False,
        samesite=samesite,
        secure=is_secure,
    )
    response.delete_cookie(
        key="user_role",
        path="/",
        httponly=False,
        samesite=samesite,
        secure=is_secure,
    )


def _handle_role_login(
    portal_name: str,
    allowed_role: UserRole,
    credentials: LoginRequest,
    request: Request,
    response: Response,
    db: Session,
) -> TokenResponse:
    """
    Authenticate a user strictly against their designated role portal.
    If credentials are valid but role does not match, logs 'wrong portal login attempt'
    without revealing real role, and returns generic 401 'Invalid credentials'.
    """
    client_ip = _get_client_ip(request)
    email_clean = credentials.email.lower().strip()

    user = db.query(User).filter(func.lower(User.email) == email_clean).first()

    valid_credentials = (
        user is not None
        and user.is_active
        and verify_password(credentials.password, user.password_hash)
    )

    if not valid_credentials or user.role != allowed_role:
        if valid_credentials and user.role != allowed_role:
            # Credentials are valid but role does not match this portal
            log_audit(
                db,
                action="wrong portal login attempt",
                entity="User",
                entity_id=str(user.id),
                actor_id=user.id,
                meta={
                    "email": email_clean,
                    "portal": portal_name,
                    "reason": "wrong portal login attempt",
                    "ip": client_ip,
                },
            )
        else:
            log_audit(
                db,
                action="LOGIN_FAILED",
                entity="User",
                entity_id=str(user.id) if user else None,
                actor_id=user.id if user else None,
                meta={"email": email_clean, "portal": portal_name, "ip": client_ip},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        subject=user.id,
        extra_claims={"email": user.email, "role": user.role.value},
    )
    refresh_token = create_refresh_token(
        subject=user.id,
        extra_claims={"email": user.email, "role": user.role.value},
    )

    _set_auth_cookies(response, access_token, refresh_token)

    log_audit(
        db,
        action=f"LOGIN_{portal_name.upper()}",
        entity="User",
        entity_id=str(user.id),
        actor_id=user.id,
        meta={"email": user.email, "role": user.role.value, "ip": client_ip},
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/admin/login", response_model=TokenResponse, summary="Admin Portal Login")
@limiter.limit(settings.LOGIN_RATE_LIMIT)
def admin_login(
    request: Request,
    response: Response,
    credentials: LoginRequest,
    db: Session = Depends(get_db),
):
    """Authenticate System Administrators (ADMIN only)."""
    return _handle_role_login("admin", UserRole.ADMIN, credentials, request, response, db)


@router.post("/coordinator/login", response_model=TokenResponse, summary="Coordinator Portal Login")
@limiter.limit(settings.LOGIN_RATE_LIMIT)
def coordinator_login(
    request: Request,
    response: Response,
    credentials: LoginRequest,
    db: Session = Depends(get_db),
):
    """Authenticate Block Coordinators (COORDINATOR only)."""
    return _handle_role_login("coordinator", UserRole.COORDINATOR, credentials, request, response, db)


@router.post("/faculty/login", response_model=TokenResponse, summary="Faculty Portal Login")
@limiter.limit(settings.LOGIN_RATE_LIMIT)
def faculty_login(
    request: Request,
    response: Response,
    credentials: LoginRequest,
    db: Session = Depends(get_db),
):
    """Authenticate Faculty Members (FACULTY only)."""
    return _handle_role_login("faculty", UserRole.FACULTY, credentials, request, response, db)


@router.post("/hod/login", response_model=TokenResponse, summary="HOD Portal Login")
@limiter.limit(settings.LOGIN_RATE_LIMIT)
def hod_login(
    request: Request,
    response: Response,
    credentials: LoginRequest,
    db: Session = Depends(get_db),
):
    """Authenticate Department Heads (HOD only)."""
    return _handle_role_login("hod", UserRole.HOD, credentials, request, response, db)


@router.post("/staff/login", status_code=status.HTTP_410_GONE, include_in_schema=False)
def disabled_staff_login():
    """Disabled shared staff login endpoint."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="The shared /staff/login endpoint has been disabled. Please use role-specific login portals.",
    )


@router.post("/refresh", response_model=TokenResponse, summary="Refresh Access Token")
def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Generate a new access token using the refresh token stored in httpOnly cookie.
    """
    client_ip = _get_client_ip(request)
    raw_refresh_token = request.cookies.get("refresh_token")

    if not raw_refresh_token:
        # Fallback to Authorization header if provided
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_refresh_token = auth_header.split(" ", 1)[1].strip()

    if not raw_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    payload = decode_refresh_token(raw_refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = payload.get("sub")
    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        )

    user = db.query(User).filter(User.id == user_id_int).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    new_access_token = create_access_token(
        subject=user.id,
        extra_claims={"email": user.email, "role": user.role.value},
    )
    new_refresh_token = create_refresh_token(
        subject=user.id,
        extra_claims={"email": user.email, "role": user.role.value},
    )

    _set_auth_cookies(response, new_access_token, new_refresh_token)

    log_audit(
        db,
        action="TOKEN_REFRESH",
        entity="User",
        entity_id=str(user.id),
        actor_id=user.id,
        meta={"email": user.email, "ip": client_ip},
    )

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/logout", response_model=MessageResponse, summary="Logout and Invalidate Cookies")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Clear authentication cookies and log the logout event."""
    client_ip = _get_client_ip(request)
    current_user = get_optional_current_user(request, db)

    _clear_auth_cookies(response)

    log_audit(
        db,
        action="LOGOUT",
        entity="User",
        entity_id=str(current_user.id) if current_user else None,
        actor_id=current_user.id if current_user else None,
        meta={"ip": client_ip, "email": current_user.email if current_user else None},
    )

    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserResponse, summary="Get Current User Profile")
def get_me(current_user: User = Depends(get_current_user)):
    """Return profile details of the currently authenticated user."""
    return UserResponse.model_validate(current_user)


@router.post("/change-password", response_model=MessageResponse, summary="Change Password")
def change_password(
    request: Request,
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Allow authenticated users to change their password.
    Requires old_password if must_change_password is False.
    Clears must_change_password flag upon successful update.
    """
    client_ip = _get_client_ip(request)
    if data.old_password:
        if not verify_password(data.old_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
    elif not current_user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is required",
        )

    current_user.password_hash = hash_password(data.new_password)
    current_user.must_change_password = False
    db.commit()

    log_audit(
        db,
        action="PASSWORD_CHANGED",
        entity="User",
        entity_id=str(current_user.id),
        actor_id=current_user.id,
        meta={"email": current_user.email, "ip": client_ip},
    )

    return MessageResponse(message="Password changed successfully")


PORTAL_ROLE_MAP = {
    "admin": UserRole.ADMIN,
    "coordinator": UserRole.COORDINATOR,
    "faculty": UserRole.FACULTY,
    "hod": UserRole.HOD,
}


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request Password Reset OTP",
)
@limiter.limit(settings.OTP_RATE_LIMIT)
def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Send a 6-digit OTP to the user's email for password recovery.
    Always returns a generic message to prevent account enumeration.
    Enforces that OTP requested from a specific portal matches the user's role.
    """
    client_ip = _get_client_ip(request)
    email_clean = data.email.lower().strip()
    portal_clean = data.portal.lower().strip() if data.portal else None
    generic_response = MessageResponse(
        message="If your email is registered, a password reset code has been sent."
    )

    if portal_clean and portal_clean not in PORTAL_ROLE_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid portal specified",
        )

    user = db.query(User).filter(func.lower(User.email) == email_clean).first()

    expected_role = PORTAL_ROLE_MAP.get(portal_clean) if portal_clean else None
    role_allowed = (
        (user.role == expected_role)
        if expected_role
        else (user.role in (UserRole.ADMIN, UserRole.COORDINATOR, UserRole.FACULTY, UserRole.HOD))
    ) if user else False

    # Generic response if user not found, inactive, or role does not match this portal
    if not user or not user.is_active or not role_allowed:
        log_audit(
            db,
            action="wrong portal forgot password attempt" if (user and user.is_active and not role_allowed) else "PASSWORD_RESET_REQUEST_UNREGISTERED",
            entity="OtpCode",
            meta={"email": email_clean, "portal": portal_clean, "ip": client_ip},
        )
        return generic_response

    purpose = f"password_reset:{portal_clean}" if portal_clean else "password_reset"

    # Check 60-second cooldown on most recent OTP
    cooldown_cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=settings.OTP_RESEND_COOLDOWN_SECONDS
    )
    latest_otp = (
        db.query(OtpCode)
        .filter(OtpCode.email == email_clean, OtpCode.purpose == purpose)
        .order_by(OtpCode.id.desc())
        .first()
    )

    if latest_otp:
        created_time = latest_otp.created_at
        if created_time.tzinfo is None:
            is_recent = created_time > cooldown_cutoff.replace(tzinfo=None)
        else:
            is_recent = created_time > cooldown_cutoff

        if is_recent:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait at least 60 seconds before requesting another verification code.",
            )

    # Generate 6-digit OTP and store hashed
    plain_otp = generate_numeric_otp(6)
    code_hash = hash_token(plain_otp)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

    otp_record = OtpCode(
        email=email_clean,
        purpose=purpose,
        code_hash=code_hash,
        expires_at=expires_at,
        attempts=0,
        used=False,
    )
    db.add(otp_record)
    db.commit()
    db.refresh(otp_record)

    # Dispatch email
    send_password_reset_otp_email(
        to_email=user.email,
        otp_code=plain_otp,
        user_name=user.name,
    )

    log_audit(
        db,
        action="PASSWORD_RESET_REQUESTED",
        entity="OtpCode",
        entity_id=str(otp_record.id),
        actor_id=user.id,
        meta={"email": email_clean, "portal": portal_clean, "ip": client_ip},
    )

    return generic_response


@router.post(
    "/verify-otp",
    response_model=VerifyOtpResponse,
    summary="Verify OTP Code",
)
@limiter.limit(settings.OTP_RATE_LIMIT)
def verify_otp_endpoint(
    request: Request,
    data: VerifyOtpRequest,
    db: Session = Depends(get_db),
):
    """Verify submitted 6-digit OTP and return a signed reset token."""
    client_ip = _get_client_ip(request)
    email_clean = data.email.lower().strip()
    portal_clean = data.portal.lower().strip() if data.portal else None

    if portal_clean and portal_clean not in PORTAL_ROLE_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid portal specified",
        )

    purpose = f"password_reset:{portal_clean}" if portal_clean else "password_reset"

    otp_record = (
        db.query(OtpCode)
        .filter(OtpCode.email == email_clean, OtpCode.purpose == purpose)
        .order_by(OtpCode.id.desc())
        .first()
    )

    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP code",
        )

    if otp_record.used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has already been used",
        )

    if otp_record.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum OTP verification attempts exceeded",
        )

    if _is_expired(otp_record.expires_at):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired",
        )

    if not verify_otp(data.otp, otp_record.code_hash):
        otp_record.attempts += 1
        db.commit()
        log_audit(
            db,
            action="OTP_VERIFY_FAILED",
            entity="OtpCode",
            entity_id=str(otp_record.id),
            meta={"email": email_clean, "portal": portal_clean, "attempts": otp_record.attempts, "ip": client_ip},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP code",
        )

    # If portal was specified, verify the user account role matches the portal
    if portal_clean:
        user = db.query(User).filter(func.lower(User.email) == email_clean).first()
        if not user or not user.is_active or user.role != PORTAL_ROLE_MAP[portal_clean]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP code",
            )

    # Valid OTP -> issue a password reset token
    extra_claims = {"type": "password_reset", "otp_id": otp_record.id}
    if portal_clean:
        extra_claims["portal"] = portal_clean

    reset_token = create_access_token(
        subject=email_clean,
        expires_delta=timedelta(minutes=15),
        extra_claims=extra_claims,
    )

    log_audit(
        db,
        action="OTP_VERIFIED",
        entity="OtpCode",
        entity_id=str(otp_record.id),
        meta={"email": email_clean, "portal": portal_clean, "ip": client_ip},
    )

    return VerifyOtpResponse(
        valid=True,
        message="OTP verified successfully",
        reset_token=reset_token,
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset Account Password",
)
@limiter.limit(settings.OTP_RATE_LIMIT)
def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Reset account password using either a verified reset_token or directly with OTP.
    """
    client_ip = _get_client_ip(request)
    email_clean = data.email.lower().strip()
    portal_clean = data.portal.lower().strip() if data.portal else None

    if portal_clean and portal_clean not in PORTAL_ROLE_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid portal specified",
        )

    purpose = f"password_reset:{portal_clean}" if portal_clean else "password_reset"
    otp_record: Optional[OtpCode] = None

    if data.reset_token:
        payload = decode_token(data.reset_token)
        if not payload or payload.get("type") != "password_reset" or payload.get("sub") != email_clean:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token",
            )
        token_portal = payload.get("portal")
        if portal_clean and token_portal and token_portal != portal_clean:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token was issued for a different portal",
            )
        otp_id = payload.get("otp_id")
        if otp_id:
            otp_record = db.query(OtpCode).filter(OtpCode.id == int(otp_id)).first()
    elif data.otp:
        otp_record = (
            db.query(OtpCode)
            .filter(OtpCode.email == email_clean, OtpCode.purpose == purpose)
            .order_by(OtpCode.id.desc())
            .first()
        )
        if not otp_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP code",
            )
        if otp_record.used:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP has already been used",
            )
        if otp_record.attempts >= settings.OTP_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum OTP verification attempts exceeded",
            )
        if _is_expired(otp_record.expires_at):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP has expired",
            )
        if not verify_otp(data.otp, otp_record.code_hash):
            otp_record.attempts += 1
            db.commit()
            log_audit(
                db,
                action="OTP_VERIFY_FAILED",
                entity="OtpCode",
                entity_id=str(otp_record.id),
                meta={"email": email_clean, "portal": portal_clean, "attempts": otp_record.attempts, "ip": client_ip},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP code",
            )

    if not otp_record or otp_record.used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification session",
        )

    user = db.query(User).filter(func.lower(User.email) == email_clean).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found or inactive",
        )

    if portal_clean and user.role != PORTAL_ROLE_MAP[portal_clean]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account does not match this portal",
        )

    # Invalidate OTP (single use) and update password
    otp_record.used = True
    user.password_hash = hash_password(data.new_password)
    db.commit()

    log_audit(
        db,
        action="PASSWORD_RESET",
        entity="User",
        entity_id=str(user.id),
        actor_id=user.id,
        meta={"email": user.email, "ip": client_ip},
    )

    return MessageResponse(message="Password reset successfully")

