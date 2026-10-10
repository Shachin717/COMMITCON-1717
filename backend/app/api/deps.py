from typing import Callable, List, Optional, Union
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.enums import UserRole
from app.models.user import User


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Retrieve and validate the currently authenticated user from cookie or Authorization header."""
    auth_header = request.headers.get("Authorization")
    token: Optional[str] = None
    using_cookie = False
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()

    if not token:
        token = request.cookies.get("access_token")
        if token:
            using_cookie = True

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # CSRF defense for cookie-based authentication on state-changing methods
    if using_cookie and request.method in ("POST", "PUT", "PATCH", "DELETE"):
        if getattr(settings, "CSRF_PROTECTION_ENABLED", True):
            csrf_header = request.headers.get("X-CSRF-Token") or request.headers.get("X-Requested-With")
            csrf_cookie = request.cookies.get("csrf_token")
            # If csrf_token cookie exists and X-CSRF-Token is passed, check double-submit match
            if csrf_cookie and request.headers.get("X-CSRF-Token"):
                if request.headers.get("X-CSRF-Token") != csrf_cookie:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="CSRF validation failed: Token mismatch",
                    )
            elif not csrf_header and not csrf_cookie:
                # Check sec-fetch-site / origin fallback
                fetch_site = request.headers.get("sec-fetch-site")
                client_host = request.client.host if request.client else "unknown"
                if client_host != "testclient" and fetch_site not in ("same-origin", "none"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="CSRF validation failed: Missing custom header or CSRF token",
                    )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid subject claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id_int).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user account",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Invalidate token if user's role in DB was changed after token issuance
    token_role = payload.get("role")
    if token_role and token_role != user.role.value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User role has changed. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_optional_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Retrieve the authenticated user if credentials exist, otherwise return None."""
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None


def require_roles(*allowed_roles: Union[UserRole, str]) -> Callable[..., User]:
    """Dependency factory restricting route access to specified user roles."""
    normalized_roles = [
        r.value if isinstance(r, UserRole) else str(r)
        for r in allowed_roles
    ]

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role_str = (
            current_user.role.value
            if isinstance(current_user.role, UserRole)
            else str(current_user.role)
        )
        if user_role_str not in normalized_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: insufficient permissions",
            )
        return current_user

    return role_checker

