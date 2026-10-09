from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database.connection import get_db
from app.models.user import User
from app.schemas.user import UserLogin, TokenResponse, UserCreate, UserResponse
from app.core.security import verify_password, get_password_hash, create_access_token, get_current_user
from app.core.exceptions import UnauthorizedException, ConflictException

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.username == payload.username)).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise UnauthorizedException("Invalid username or password")
    if not user.is_active:
        raise UnauthorizedException("Account is disabled")

    token = create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": user.id, "email": user.email}
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        username=user.username,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.scalars(
        select(User).where((User.username == payload.username) | (User.email == payload.email))
    ).first()
    if existing:
        raise ConflictException("Username or email already exists")

    hashed = get_password_hash(payload.password)
    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hashed,
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

