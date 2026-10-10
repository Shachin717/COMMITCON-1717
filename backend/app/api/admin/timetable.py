import math
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.timetable import (
    TimetableEntryCreate,
    TimetableEntryResponse,
    TimetableEntryUpdate,
    TimetableImportResponse,
)
from app.services.admin import (
    create_timetable_entry,
    delete_timetable_entry,
    get_timetable_entry_by_id,
    import_timetable_csv,
    list_timetable_entries,
    update_timetable_entry,
)

router = APIRouter(prefix="/timetable", tags=["Admin Timetable"])


@router.post(
    "",
    response_model=TimetableEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a timetable entry",
)
def create_timetable_entry_route(
    data: TimetableEntryCreate,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    entry = create_timetable_entry(db, data, actor_id=current_admin.id)
    return TimetableEntryResponse.model_validate(entry)


@router.get(
    "",
    response_model=PaginatedResponse[TimetableEntryResponse],
    summary="List timetable entries with filters and search",
)
def list_timetable_entries_route(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search by subject or faculty name"),
    room_id: Optional[int] = Query(None, description="Filter by room"),
    day_of_week: Optional[int] = Query(None, ge=0, le=6, description="Filter by day of week (0=Mon, 6=Sun)"),
    slot_id: Optional[int] = Query(None, description="Filter by slot"),
    department_id: Optional[int] = Query(None, description="Filter by department"),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    items, total = list_timetable_entries(
        db,
        page=page,
        page_size=page_size,
        search=search,
        room_id=room_id,
        day_of_week=day_of_week,
        slot_id=slot_id,
        department_id=department_id,
    )
    pages = math.ceil(total / page_size) if page_size > 0 else 0
    return PaginatedResponse(
        items=[TimetableEntryResponse.model_validate(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/{entry_id}",
    response_model=TimetableEntryResponse,
    summary="Get timetable entry by ID",
)
def get_timetable_entry_route(
    entry_id: int,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    entry = get_timetable_entry_by_id(db, entry_id)
    return TimetableEntryResponse.model_validate(entry)


@router.put(
    "/{entry_id}",
    response_model=TimetableEntryResponse,
    summary="Update timetable entry",
)
@router.patch(
    "/{entry_id}",
    response_model=TimetableEntryResponse,
    summary="Update timetable entry",
)
def update_timetable_entry_route(
    entry_id: int,
    data: TimetableEntryUpdate,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    entry = update_timetable_entry(db, entry_id, data, actor_id=current_admin.id)
    return TimetableEntryResponse.model_validate(entry)


@router.delete(
    "/{entry_id}",
    response_model=MessageResponse,
    summary="Delete timetable entry",
)
def delete_timetable_entry_route(
    entry_id: int,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    delete_timetable_entry(db, entry_id, actor_id=current_admin.id)
    return MessageResponse(message=f"Timetable entry {entry_id} deleted successfully")


@router.post(
    "/import-csv",
    response_model=TimetableImportResponse,
    summary="Import timetable entries from CSV file upload",
)
async def import_timetable_csv_route(
    file: UploadFile = File(..., description="CSV file with timetable entries"),
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

    return import_timetable_csv(db, csv_text, actor_id=current_admin.id)

