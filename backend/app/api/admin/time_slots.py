import math
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.time_slot import (
    TimeSlotCreate,
    TimeSlotResponse,
    TimeSlotUpdate,
)
from app.services.admin import (
    create_time_slot,
    delete_time_slot,
    get_time_slot_by_id,
    list_time_slots,
    update_time_slot,
)

router = APIRouter(prefix="/time-slots", tags=["Admin Time Slots"])


@router.post(
    "",
    response_model=TimeSlotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new time slot",
)
def create_time_slot_route(
    data: TimeSlotCreate,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    slot = create_time_slot(db, data, actor_id=current_admin.id)
    return TimeSlotResponse.model_validate(slot)


@router.get(
    "",
    response_model=PaginatedResponse[TimeSlotResponse],
    summary="List time slots ordered by schedule order",
)
def list_time_slots_route(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search by slot label"),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    items, total = list_time_slots(db, page=page, page_size=page_size, search=search)
    pages = math.ceil(total / page_size) if page_size > 0 else 0
    return PaginatedResponse(
        items=[TimeSlotResponse.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/{slot_id}",
    response_model=TimeSlotResponse,
    summary="Get time slot by ID",
)
def get_time_slot_route(
    slot_id: int,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    slot = get_time_slot_by_id(db, slot_id)
    return TimeSlotResponse.model_validate(slot)


@router.put(
    "/{slot_id}",
    response_model=TimeSlotResponse,
    summary="Update time slot",
)
@router.patch(
    "/{slot_id}",
    response_model=TimeSlotResponse,
    summary="Update time slot",
)
def update_time_slot_route(
    slot_id: int,
    data: TimeSlotUpdate,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    slot = update_time_slot(db, slot_id, data, actor_id=current_admin.id)
    return TimeSlotResponse.model_validate(slot)


@router.delete(
    "/{slot_id}",
    response_model=MessageResponse,
    summary="Delete time slot",
)
def delete_time_slot_route(
    slot_id: int,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    delete_time_slot(db, slot_id, actor_id=current_admin.id)
    return MessageResponse(message=f"Time slot {slot_id} deleted successfully")

