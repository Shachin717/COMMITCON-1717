import math
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.enums import BookingStatus, RequesterType, UserRole
from app.models.user import User
from app.schemas.booking import BookingResponse
from app.schemas.common import PaginatedResponse
from app.services.admin import export_bookings_csv, list_bookings

router = APIRouter(prefix="/bookings", tags=["Admin Bookings"])


@router.get(
    "",
    response_model=PaginatedResponse[BookingResponse],
    summary="Get booking history with extensive filtering, search, and pagination",
)
def list_bookings_route(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    date_from: Optional[date] = Query(None, description="Start date filter"),
    date_to: Optional[date] = Query(None, description="End date filter"),
    block_id: Optional[int] = Query(None, description="Filter by physical block"),
    room_id: Optional[int] = Query(None, description="Filter by room"),
    department_id: Optional[int] = Query(None, description="Filter by department"),
    status: Optional[BookingStatus] = Query(None, description="Filter by booking status"),
    requester: Optional[str] = Query(None, description="Filter by requester name, email, or roll no"),
    requester_type: Optional[RequesterType] = Query(None, description="Filter by requester type (STUDENT/FACULTY)"),
    search: Optional[str] = Query(None, description="Search across reference, name, email, roll no, purpose"),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    items, total = list_bookings(
        db,
        page=page,
        page_size=page_size,
        date_from=date_from,
        date_to=date_to,
        block_id=block_id,
        room_id=room_id,
        department_id=department_id,
        status=status,
        requester=requester,
        requester_type=requester_type,
        search=search,
    )
    pages = math.ceil(total / page_size) if page_size > 0 else 0
    return PaginatedResponse(
        items=[BookingResponse.model_validate(b) for b in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/export-csv",
    summary="Export booking history matching filters to CSV",
)
@router.get(
    "/export",
    summary="Export booking history matching filters to CSV",
)
def export_bookings_csv_route(
    date_from: Optional[date] = Query(None, description="Start date filter"),
    date_to: Optional[date] = Query(None, description="End date filter"),
    block_id: Optional[int] = Query(None, description="Filter by physical block"),
    room_id: Optional[int] = Query(None, description="Filter by room"),
    department_id: Optional[int] = Query(None, description="Filter by department"),
    status: Optional[BookingStatus] = Query(None, description="Filter by booking status"),
    requester: Optional[str] = Query(None, description="Filter by requester name, email, or roll no"),
    requester_type: Optional[RequesterType] = Query(None, description="Filter by requester type"),
    search: Optional[str] = Query(None, description="Search term"),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    csv_data = export_bookings_csv(
        db,
        date_from=date_from,
        date_to=date_to,
        block_id=block_id,
        room_id=room_id,
        department_id=department_id,
        status=status,
        requester=requester,
        requester_type=requester_type,
        search=search,
    )
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=bookings_export.csv",
        },
    )

