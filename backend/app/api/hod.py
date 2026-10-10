from datetime import date
import math
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.enums import BookingStatus, RoomType, UserRole
from app.models.user import User
from app.schemas.booking import BookingResponse
from app.schemas.common import PaginatedResponse
from app.schemas.hod import (
    HodDecisionRequest,
    HodLabResponse,
    HodPendingApprovalsResponse,
    HodRoomOption,
    HodSummaryResponse,
)
from app.services.hod import (
    decide_hod_booking,
    export_hod_bookings_csv,
    get_hod_department_summary,
    get_hod_pending_approvals,
    list_hod_bookings_history,
    list_hod_department_labs,
    list_hod_department_rooms,
)

router = APIRouter(
    prefix="/hod",
    tags=["HOD"],
    dependencies=[Depends(require_roles(UserRole.HOD))],
)


@router.get(
    "/summary",
    response_model=HodSummaryResponse,
    summary="Get department utilization summary, KPIs, and chart data for HOD",
)
def get_hod_department_summary_route(
    current_user: User = Depends(require_roles(UserRole.HOD)),
    db: Session = Depends(get_db),
):
    return get_hod_department_summary(db=db, user=current_user)


@router.get(
    "/overview",
    response_model=HodSummaryResponse,
    summary="Alias to get department utilization summary for HOD",
)
def get_hod_department_overview_alias_route(
    current_user: User = Depends(require_roles(UserRole.HOD)),
    db: Session = Depends(get_db),
):
    return get_hod_department_summary(db=db, user=current_user)


@router.get(
    "/labs",
    response_model=List[HodLabResponse],
    summary="List all laboratories owned by the department with upcoming usage",
)
def list_hod_department_labs_route(
    current_user: User = Depends(require_roles(UserRole.HOD)),
    db: Session = Depends(get_db),
):
    return list_hod_department_labs(db=db, user=current_user)


@router.get(
    "/rooms",
    response_model=List[HodRoomOption],
    summary="List department rooms for history filter dropdowns",
)
def list_hod_department_rooms_route(
    current_user: User = Depends(require_roles(UserRole.HOD)),
    db: Session = Depends(get_db),
):
    return list_hod_department_rooms(db=db, user=current_user)


@router.get(
    "/bookings/history",
    response_model=PaginatedResponse[BookingResponse],
    summary="Get bookings history of classes and labs for HOD's department",
)
def get_hod_bookings_history_route(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    status: Optional[BookingStatus] = Query(None, description="Filter by booking status"),
    date_from: Optional[date] = Query(None, description="Start date filter"),
    date_to: Optional[date] = Query(None, description="End date filter"),
    room_id: Optional[int] = Query(None, description="Filter by specific room ID"),
    student: Optional[str] = Query(None, description="Filter by student roll number, name, or email"),
    room_type: Optional[RoomType] = Query(None, description="Filter by room type"),
    search: Optional[str] = Query(None, description="Search keyword across fields"),
    current_user: User = Depends(require_roles(UserRole.HOD)),
    db: Session = Depends(get_db),
):
    items, total = list_hod_bookings_history(
        db,
        user=current_user,
        page=page,
        page_size=page_size,
        status_filter=status,
        date_from=date_from,
        date_to=date_to,
        room_id=room_id,
        student=student,
        room_type=room_type,
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
    "/bookings/export",
    summary="Export bookings history for HOD's department to CSV",
)
def export_hod_bookings_csv_route(
    status: Optional[BookingStatus] = Query(None, description="Filter by booking status"),
    date_from: Optional[date] = Query(None, description="Start date filter"),
    date_to: Optional[date] = Query(None, description="End date filter"),
    room_id: Optional[int] = Query(None, description="Filter by specific room ID"),
    student: Optional[str] = Query(None, description="Filter by student roll number, name, or email"),
    room_type: Optional[RoomType] = Query(None, description="Filter by room type"),
    search: Optional[str] = Query(None, description="Search keyword across fields"),
    current_user: User = Depends(require_roles(UserRole.HOD)),
    db: Session = Depends(get_db),
):
    csv_data = export_hod_bookings_csv(
        db,
        user=current_user,
        status_filter=status,
        date_from=date_from,
        date_to=date_to,
        room_id=room_id,
        student=student,
        room_type=room_type,
        search=search,
    )
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=department_bookings_history.csv"
        },
    )


@router.get(
    "/approvals/pending",
    response_model=HodPendingApprovalsResponse,
    summary="Get pending approvals for LAB / EXAM_HALL bookings of department",
)
def get_hod_pending_approvals_route(
    current_user: User = Depends(require_roles(UserRole.HOD)),
    db: Session = Depends(get_db),
):
    return get_hod_pending_approvals(db=db, user=current_user)


@router.post(
    "/bookings/{booking_id}/decision",
    response_model=BookingResponse,
    summary="Approve or reject a COORDINATOR_APPROVED LAB/EXAM_HALL booking for HOD's department",
)
def decide_hod_booking_route(
    booking_id: int,
    decision_in: HodDecisionRequest,
    current_user: User = Depends(require_roles(UserRole.HOD)),
    db: Session = Depends(get_db),
):
    booking = decide_hod_booking(
        db=db,
        booking_id=booking_id,
        user=current_user,
        decision_in=decision_in,
    )
    return BookingResponse.model_validate(booking)
