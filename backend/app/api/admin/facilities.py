import math
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.facility import (
    FacilityCreate,
    FacilityResponse,
    FacilityUpdate,
)
from app.services.admin import (
    create_facility,
    delete_facility,
    get_facility_by_id,
    list_facilities,
    update_facility,
)

router = APIRouter(prefix="/facilities", tags=["Admin Facilities"])


@router.post(
    "",
    response_model=FacilityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new facility / amenity",
)
def create_facility_route(
    data: FacilityCreate,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    fac = create_facility(db, data, actor_id=current_admin.id)
    return FacilityResponse.model_validate(fac)


@router.get(
    "",
    response_model=PaginatedResponse[FacilityResponse],
    summary="List facilities with pagination and search",
)
def list_facilities_route(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search by facility name"),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    items, total = list_facilities(db, page=page, page_size=page_size, search=search)
    pages = math.ceil(total / page_size) if page_size > 0 else 0
    return PaginatedResponse(
        items=[FacilityResponse.model_validate(f) for f in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/{facility_id}",
    response_model=FacilityResponse,
    summary="Get facility by ID",
)
def get_facility_route(
    facility_id: int,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    fac = get_facility_by_id(db, facility_id)
    return FacilityResponse.model_validate(fac)


@router.put(
    "/{facility_id}",
    response_model=FacilityResponse,
    summary="Update facility",
)
@router.patch(
    "/{facility_id}",
    response_model=FacilityResponse,
    summary="Update facility",
)
def update_facility_route(
    facility_id: int,
    data: FacilityUpdate,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    fac = update_facility(db, facility_id, data, actor_id=current_admin.id)
    return FacilityResponse.model_validate(fac)


@router.delete(
    "/{facility_id}",
    response_model=MessageResponse,
    summary="Delete facility",
)
def delete_facility_route(
    facility_id: int,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    delete_facility(db, facility_id, actor_id=current_admin.id)
    return MessageResponse(message=f"Facility {facility_id} deleted successfully")

