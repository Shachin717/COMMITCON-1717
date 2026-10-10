import math
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.department import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
)
from app.services.admin import (
    create_department,
    delete_department,
    get_department_by_id,
    list_departments,
    toggle_department_hod_approval,
    update_department,
)

router = APIRouter(prefix="/departments", tags=["Admin Departments"])


@router.post(
    "",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new department",
)
def create_department_route(
    data: DepartmentCreate,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    dept = create_department(db, data, actor_id=current_admin.id)
    return DepartmentResponse.model_validate(dept)


@router.get(
    "",
    response_model=PaginatedResponse[DepartmentResponse],
    summary="List departments with pagination and search",
)
def list_departments_route(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search by department name or code"),
    hod_approval_required: Optional[bool] = Query(None, description="Filter by HOD approval required flag"),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    items, total = list_departments(
        db,
        page=page,
        page_size=page_size,
        search=search,
        hod_approval_required=hod_approval_required,
    )
    pages = math.ceil(total / page_size) if page_size > 0 else 0
    return PaginatedResponse(
        items=[DepartmentResponse.model_validate(d) for d in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/{department_id}",
    response_model=DepartmentResponse,
    summary="Get department by ID",
)
def get_department_route(
    department_id: int,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    dept = get_department_by_id(db, department_id)
    return DepartmentResponse.model_validate(dept)


@router.put(
    "/{department_id}",
    response_model=DepartmentResponse,
    summary="Update department",
)
@router.patch(
    "/{department_id}",
    response_model=DepartmentResponse,
    summary="Update department",
)
def update_department_route(
    department_id: int,
    data: DepartmentUpdate,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    dept = update_department(db, department_id, data, actor_id=current_admin.id)
    return DepartmentResponse.model_validate(dept)


@router.post(
    "/{department_id}/toggle-hod-approval",
    response_model=DepartmentResponse,
    summary="Toggle HOD approval requirement for department",
)
@router.patch(
    "/{department_id}/toggle-hod-approval",
    response_model=DepartmentResponse,
    summary="Toggle HOD approval requirement for department",
)
def toggle_hod_approval_route(
    department_id: int,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    dept = toggle_department_hod_approval(db, department_id, actor_id=current_admin.id)
    return DepartmentResponse.model_validate(dept)


@router.delete(
    "/{department_id}",
    response_model=MessageResponse,
    summary="Delete department",
)
def delete_department_route(
    department_id: int,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    delete_department(db, department_id, actor_id=current_admin.id)
    return MessageResponse(message=f"Department {department_id} deleted successfully")

