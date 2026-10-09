from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings
from app.core.exceptions import UnauthorizedException, ForbiddenException

security_scheme = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if isinstance(plain_password, str):
        plain_bytes = plain_password.encode("utf-8")
    else:
        plain_bytes = plain_password
    if isinstance(hashed_password, str):
        hash_bytes = hashed_password.encode("utf-8")
    else:
        hash_bytes = hashed_password
    return bcrypt.checkpw(plain_bytes, hash_bytes)


def get_password_hash(password: str) -> str:
    if isinstance(password, str):
        password_bytes = password.encode("utf-8")
    else:
        password_bytes = password
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedException(detail="Token has expired")
    except jwt.PyJWTError:
        raise UnauthorizedException(detail="Invalid token")


def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Dict[str, Any]:
    """
    Returns current user payload. In development, if no token provided,
    returns default admin user to allow frictionless local development and testing,
    while still enforcing proper authorization when a Bearer token is provided.
    """
    if auth is None:
        if settings.APP_ENV in ("development", "testing"):
            return {
                "sub": "admin",
                "role": "ADMIN",
                "is_admin": True,
                "email": "admin@college.edu",
                "user_id": 1,
            }
        raise UnauthorizedException(detail="Authentication required")
    
    token = auth.credentials
    payload = decode_token(token)
    return payload


def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    role = current_user.get("role", "").upper()
    if role != "ADMIN" and not current_user.get("is_admin", False):
        raise ForbiddenException(detail="Administrator privileges required")
    return current_user


def require_hod(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    role = current_user.get("role", "").upper()
    if role != "HOD":
        raise ForbiddenException(detail="HOD privileges required")
    return current_user


def require_authenticated(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Require any authenticated user (not just admin)"""
    return current_user
