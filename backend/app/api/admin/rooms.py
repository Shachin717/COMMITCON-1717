import math
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.enums import RoomStatus, RoomType, UserRole
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.room import (
    RoomCreate,
    RoomImportResponse,
    RoomResponse,
    RoomStatusUpdate,
    RoomUpdate,
)
from app.services.admin import (
    create_room,
    delete_room,
    get_room_by_id,
    import_rooms_csv,
    list_rooms,
    set_room_status,
    update_room,
)

router = APIRouter(prefix="/rooms", tags=["Admin Rooms"])


@router.post(
    "",
    response_model=RoomResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create room (classroom, lab, exam hall, seminar hall)",
)
def create_room_route(
    data: RoomCreate,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    room = create_room(db, data, actor_id=current_admin.id)
    return RoomResponse.model_validate(room)


@router.get(
    "",
    response_model=PaginatedResponse[RoomResponse],
    summary="List rooms with filters, search, and pagination",
)
def list_rooms_route(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search by room name"),
    block_id: Optional[int] = Query(None, description="Filter by physical block"),
    department_id: Optional[int] = Query(None, description="Filter by department"),
    room_type: Optional[RoomType] = Query(None, description="Filter by room type"),
    status: Optional[RoomStatus] = Query(None, description="Filter by status (ACTIVE/MAINTENANCE)"),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    items, total = list_rooms(
        db,
        page=page,
        page_size=page_size,
        search=search,
        block_id=block_id,
        department_id=department_id,
        room_type=room_type,
        status=status,
    )
    pages = math.ceil(total / page_size) if page_size > 0 else 0
    return PaginatedResponse(
        items=[RoomResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/{room_id}",
    response_model=RoomResponse,
    summary="Get room by ID",
)
def get_room_route(
    room_id: int,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    room = get_room_by_id(db, room_id)
    return RoomResponse.model_validate(room)


@router.put(
    "/{room_id}",
    response_model=RoomResponse,
    summary="Update room details",
)
@router.patch(
    "/{room_id}",
    response_model=RoomResponse,
    summary="Update room details",
)
def update_room_route(
    room_id: int,
    data: RoomUpdate,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    room = update_room(db, room_id, data, actor_id=current_admin.id)
    return RoomResponse.model_validate(room)


@router.patch(
    "/{room_id}/status",
    response_model=RoomResponse,
    summary="Set room status (ACTIVE / MAINTENANCE) with optional maintenance note",
)
@router.post(
    "/{room_id}/status",
    response_model=RoomResponse,
    summary="Set room status (ACTIVE / MAINTENANCE) with optional maintenance note",
)
def set_room_status_route(
    room_id: int,
    data: RoomStatusUpdate,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    room = set_room_status(
        db,
        room_id=room_id,
        status=data.status,
        maintenance_note=data.maintenance_note,
        actor_id=current_admin.id,
    )
    return RoomResponse.model_validate(room)


@router.delete(
    "/{room_id}",
    response_model=MessageResponse,
    summary="Delete room",
)
def delete_room_route(
    room_id: int,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    delete_room(db, room_id, actor_id=current_admin.id)
    return MessageResponse(message=f"Room {room_id} deleted successfully")


@router.post(
    "/import-csv",
    response_model=RoomImportResponse,
    summary="Bulk import rooms from CSV file upload",
)
async def import_rooms_csv_route(
    file: UploadFile = File(..., description="CSV file with room entries"),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    content_bytes = await file.read()
    try:
        csv_text = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            csv_text = content_bytes.decode("latin-1")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to decode CSV file as UTF-8 or text",
            )

    return import_rooms_csv(db, csv_text, actor_id=current_admin.id)


