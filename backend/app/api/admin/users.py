import math
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.user import (
    AdminUserCreate,
    AdminUserCreateResponse,
    UserResponse,
    UserUpdate,
)
from app.services.admin import (
    create_admin_user,
    get_user_by_id,
    list_users,
    set_user_active_status,
    update_user,
)

router = APIRouter(prefix="/users", tags=["Admin Users"])


@router.post(
    "",
    response_model=AdminUserCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create staff account (HOD / COORDINATOR / FACULTY)",
)
def create_user_route(
    data: AdminUserCreate,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    user, temp_password = create_admin_user(db, data, actor_id=current_admin.id)
    resp = AdminUserCreateResponse.model_validate(user)
    resp.temporary_password = temp_password
    return resp


@router.get(
    "",
    response_model=PaginatedResponse[UserResponse],
    summary="List all users with pagination, search, and filters",
)
def list_users_route(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search by name, email, or phone"),
    role: Optional[UserRole] = Query(None, description="Filter by user role"),
    department_id: Optional[int] = Query(None, description="Filter by department"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    items, total = list_users(
        db,
        page=page,
        page_size=page_size,
        search=search,
        role=role,
        department_id=department_id,
        is_active=is_active,
    )
    pages = math.ceil(total / page_size) if page_size > 0 else 0
    return PaginatedResponse(
        items=[UserResponse.model_validate(u) for u in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
)
def get_user_route(
    user_id: int,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    user = get_user_by_id(db, user_id)
    return UserResponse.model_validate(user)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user details",
)
@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user details",
)
def update_user_route(
    user_id: int,
    data: UserUpdate,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    user = update_user(db, user_id, data, actor_id=current_admin.id)
    return UserResponse.model_validate(user)


@router.post(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    summary="Deactivate user account",
)
def deactivate_user_route(
    user_id: int,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    user = set_user_active_status(db, user_id, is_active=False, actor_id=current_admin.id)
    return UserResponse.model_validate(user)


@router.post(
    "/{user_id}/activate",
    response_model=UserResponse,
    summary="Activate user account",
)
def activate_user_route(
    user_id: int,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    user = set_user_active_status(db, user_id, is_active=True, actor_id=current_admin.id)
    return UserResponse.model_validate(user)

