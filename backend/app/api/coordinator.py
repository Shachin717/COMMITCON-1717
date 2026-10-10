from datetime import date
import math
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.enums import BookingStatus, RoomStatus, UserRole
from app.models.user import User
from app.schemas.booking import BookingResponse
from app.schemas.common import PaginatedResponse
from app.schemas.coordinator import (
    BlockOverviewResponse,
    BlockedRoomItem,
    BlockedRoomsResponse,
    ConfirmRelocationRequest,
    ConfirmRelocationResponse,
    CoordinatorBlockResponse,
    CoordinatorBlocksResponse,
    CoordinatorBulkDecisionRequest,
    CoordinatorBulkDecisionResponse,
    CoordinatorDecisionRequest,
    CoordinatorRoomBlockCreate,
    CoordinatorRoomBlockPreviewRequest,
    CoordinatorRoomResponse,
    CoordinatorRoomsResponse,
    RoomBlockBatchResponse,
    RoomBlockBulkReleaseRequest,
    RoomBlockBulkReleaseResponse,
    RoomBlockPreviewResponse,
    RoomBlockReleaseResponse,
    RoomMaintenanceReleaseResponse,
    RoomOverviewItem,
)
from app.schemas.public import TimetableResponse
from app.services.coordinator import (
    bulk_decide_coordinator_bookings,
    bulk_release_coordinator_room_blocks,
    confirm_room_block_and_relocate,
    create_coordinator_room_blocks,
    decide_coordinator_booking,
    export_coordinator_bookings_csv,
    get_all_blocks_overview,
    get_coordinator_blocks,
    get_coordinator_rooms,
    get_coordinator_timetable,
    list_coordinator_bookings,
    list_coordinator_room_blocks,
    preview_room_block_relocations,
    release_coordinator_room_block,
    release_room_maintenance,
)

router = APIRouter(
    prefix="/coordinator",
    tags=["Coordinator"],
    dependencies=[Depends(require_roles(UserRole.COORDINATOR))],
)


@router.get(
    "/blocks",
    response_model=CoordinatorBlocksResponse,
    summary="Get blocks assigned to the coordinator",
)
def get_coordinator_blocks_route(
    current_user: User = Depends(require_roles(UserRole.COORDINATOR)),
    db: Session = Depends(get_db),
):
    blocks = get_coordinator_blocks(db, current_user)
    items = [CoordinatorBlockResponse.model_validate(b) for b in blocks]
    return CoordinatorBlocksResponse(items=items, total=len(items))


@router.get(
    "/rooms",
    response_model=CoordinatorRoomsResponse,
    summary="Get rooms in coordinator's assigned blocks",
)
def get_coordinator_rooms_route(
    block_id: Optional[int] = Query(None, description="Optional block ID filter"),
    search: Optional[str] = Query(None, description="Search rooms by name"),
    status: Optional[RoomStatus] = Query(None, description="Filter by room status (ACTIVE / MAINTENANCE)"),
    current_user: User = Depends(require_roles(UserRole.COORDINATOR)),
    db: Session = Depends(get_db),
):
    rooms = get_coordinator_rooms(
        db,
        user=current_user,
        block_id=block_id,
        search=search,
        status_filter=status,
    )
    items = [
        CoordinatorRoomResponse(
            id=r.id,
            name=r.name,
            block=r.block.name if r.block else f"Block {r.block_id}",
            block_id=r.block_id,
            floor=r.floor,
            room_type=r.room_type,
            capacity=r.capacity,
            status=r.status,
            maintenance_note=r.maintenance_note,
        )
        for r in rooms
    ]
    return CoordinatorRoomsResponse(items=items, total=len(items))




@router.get(
    "/bookings",
    response_model=PaginatedResponse[BookingResponse],
    summary="Get pending/all bookings of my assigned blocks with filters",
)
def get_coordinator_bookings_route(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    status: Optional[BookingStatus] = Query(None, description="Filter by booking status"),
    only_pending: bool = Query(False, description="Filter only PENDING status"),
    date_from: Optional[date] = Query(None, description="Start date filter"),
    date_to: Optional[date] = Query(None, description="End date filter"),
    room_id: Optional[int] = Query(None, description="Filter by room"),
    block_id: Optional[int] = Query(None, description="Filter by block (must be assigned)"),
    search: Optional[str] = Query(None, description="Search across reference, student name, email, roll no, purpose"),
    current_user: User = Depends(require_roles(UserRole.COORDINATOR)),
    db: Session = Depends(get_db),
):
    items, total = list_coordinator_bookings(
        db,
        user=current_user,
        page=page,
        page_size=page_size,
        status_filter=status,
        only_pending=only_pending,
        date_from=date_from,
        date_to=date_to,
        room_id=room_id,
        block_id=block_id,
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
    "/bookings/pending",
    response_model=PaginatedResponse[BookingResponse],
    summary="Shortcut: Get pending bookings of my assigned blocks",
)
def get_coordinator_pending_bookings_route(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    date_from: Optional[date] = Query(None, description="Start date filter"),
    date_to: Optional[date] = Query(None, description="End date filter"),
    room_id: Optional[int] = Query(None, description="Filter by room"),
    block_id: Optional[int] = Query(None, description="Filter by block"),
    search: Optional[str] = Query(None, description="Search keyword"),
    current_user: User = Depends(require_roles(UserRole.COORDINATOR)),
    db: Session = Depends(get_db),
):
    items, total = list_coordinator_bookings(
        db,
        user=current_user,
        page=page,
        page_size=page_size,
        only_pending=True,
        date_from=date_from,
        date_to=date_to,
        room_id=room_id,
        block_id=block_id,
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


@router.post(
    "/bookings/{booking_id}/decision",
    response_model=BookingResponse,
    summary="Approve or reject a booking in assigned block with optional note",
)
def decide_coordinator_booking_route(
    booking_id: int,
    decision_in: CoordinatorDecisionRequest,
    current_user: User = Depends(require_roles(UserRole.COORDINATOR)),
    db: Session = Depends(get_db),
):
    booking = decide_coordinator_booking(
        db=db,
        booking_id=booking_id,
        user=current_user,
        decision_in=decision_in,
    )
    return BookingResponse.model_validate(booking)


@router.post(
    "/bookings/bulk-decision",
    response_model=CoordinatorBulkDecisionResponse,
    summary="Bulk approve or reject bookings in assigned blocks",
)
def bulk_decide_coordinator_booking_route(
    data: CoordinatorBulkDecisionRequest,
    current_user: User = Depends(require_roles(UserRole.COORDINATOR)),
    db: Session = Depends(get_db),
):
    return bulk_decide_coordinator_bookings(
        db=db,
        user=current_user,
        data=data,
    )


@router.get(
    "/overview",
    response_model=BlockOverviewResponse,
    summary="Get overview of ALL blocks: booked rooms and remaining free rooms for a date/slot",
)
def get_blocks_overview_route(
    date: date = Query(..., description="Target date (YYYY-MM-DD)"),
    slot_id: Optional[int] = Query(None, description="Specific time slot ID (optional)"),
    current_user: User = Depends(require_roles(UserRole.COORDINATOR)),
    db: Session = Depends(get_db),
):
    return get_all_blocks_overview(
        db=db,
        user=current_user,
        target_date=date,
        slot_id=slot_id,
    )


@router.post(
    "/room-blocks/preview",
    response_model=RoomBlockPreviewResponse,
    summary="Preview affected bookings and suggested replacement rooms before confirming room block",
)
def preview_room_block_route(
    data: CoordinatorRoomBlockPreviewRequest,
    current_user: User = Depends(require_roles(UserRole.COORDINATOR)),
    db: Session = Depends(get_db),
):
    return preview_room_block_relocations(
        db=db,
        user=current_user,
        data=data,
    )


@router.post(
    "/room-blocks/confirm-relocation",
    response_model=ConfirmRelocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Confirm room block and relocate affected bookings with requester notifications",
)
def confirm_room_block_relocation_route(
    data: ConfirmRelocationRequest,
    current_user: User = Depends(require_roles(UserRole.COORDINATOR)),
    db: Session = Depends(get_db),
):
    return confirm_room_block_and_relocate(
        db=db,
        user=current_user,
        data=data,
    )


@router.post(
    "/room-blocks",
    response_model=RoomBlockBatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Block a room for MAINTENANCE or EXAM (creating RoomBlock, with date range and slots) and optionally mark it as EXAM_HALL usage",
)
def create_room_block_route(
    data: CoordinatorRoomBlockCreate,
    current_user: User = Depends(require_roles(UserRole.COORDINATOR)),
    db: Session = Depends(get_db),
):
    return create_coordinator_room_blocks(
        db=db,
        user=current_user,
        data=data,
    )


@router.get(
    "/room-blocks",
    response_model=BlockedRoomsResponse,
    summary="Get paginated list of blocked rooms for assigned blocks with status/date/reason filters and summary counts",
)
def get_coordinator_room_blocks_route(
    status: Optional[str] = Query("all", description="Status filter: active, upcoming, past, all"),
    block_id: Optional[int] = Query(None, description="Optional block ID filter"),
    room_id: Optional[int] = Query(None, description="Optional room ID filter"),
    reason: Optional[str] = Query(None, description="Filter by reason (MAINTENANCE, EXAM, OTHER)"),
    date_from: Optional[date] = Query(None, description="Start date filter"),
    date_to: Optional[date] = Query(None, description="End date filter"),
    search: Optional[str] = Query(None, description="Search by room name or block note"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    current_user: User = Depends(require_roles(UserRole.COORDINATOR)),
    db: Session = Depends(get_db),
):
    return list_coordinator_room_blocks(
        db=db,
        user=current_user,
        status_filter=status,
        block_id=block_id,
        room_id=room_id,
        reason=reason,
        date_from=date_from,
        date_to=date_to,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.delete(
    "/room-blocks/{block_id}",
    response_model=BlockedRoomItem,
    summary="Release a single room block (soft delete/release) by ID",
)
def delete_coordinator_room_block_route(
    block_id: int,
    current_user: User = Depends(require_roles(UserRole.COORDINATOR)),
    db: Session = Depends(get_db),
):
    return release_coordinator_room_block(
        db=db,
        user=current_user,
        block_id=block_id,
    )


@router.post(
    "/room-blocks/{block_id}/release",
    response_model=BlockedRoomItem,
    summary="Release a single room block by ID",
)
def release_coordinator_room_block_route(
    block_id: int,
    current_user: User = Depends(require_roles(UserRole.COORDINATOR)),
    db: Session = Depends(get_db),
):
    return release_coordinator_room_block(
        db=db,
        user=current_user,
        block_id=block_id,
    )


@router.post(
    "/room-blocks/release-bulk",
    response_model=RoomBlockBulkReleaseResponse,
    summary="Bulk release room blocks by list of IDs or by room and date range",
)
def bulk_release_coordinator_room_blocks_route(
    data: RoomBlockBulkReleaseRequest,
    current_user: User = Depends(require_roles(UserRole.COORDINATOR)),
    db: Session = Depends(get_db),
):
    return bulk_release_coordinator_room_blocks(
        db=db,
        user=current_user,
        data=data,
    )


@router.post(
    "/rooms/{room_id}/release-maintenance",
    response_model=RoomMaintenanceReleaseResponse,
    summary="Set room status back to ACTIVE, clear maintenance_note, and release today's maintenance blocks",
)
def release_coordinator_room_maintenance_route(
    room_id: int,
    current_user: User = Depends(require_roles(UserRole.COORDINATOR)),
    db: Session = Depends(get_db),
):
    return release_room_maintenance(
        db=db,
        user=current_user,
        room_id=room_id,
    )



@router.get(
    "/history",
    response_model=PaginatedResponse[BookingResponse],
    summary="Get decided booking history of assigned blocks",
)
def get_coordinator_history_route(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    status: Optional[BookingStatus] = Query(None, description="Filter by status (APPROVED, REJECTED, etc.)"),
    date_from: Optional[date] = Query(None, description="Start date filter"),
    date_to: Optional[date] = Query(None, description="End date filter"),
    room_id: Optional[int] = Query(None, description="Filter by room"),
    block_id: Optional[int] = Query(None, description="Filter by block"),
    search: Optional[str] = Query(None, description="Search keyword"),
    current_user: User = Depends(require_roles(UserRole.COORDINATOR)),
    db: Session = Depends(get_db),
):
    items, total = list_coordinator_bookings(
        db,
        user=current_user,
        page=page,
        page_size=page_size,
        status_filter=status,
        only_pending=False,
        date_from=date_from,
        date_to=date_to,
        room_id=room_id,
        block_id=block_id,
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
    "/timetable",
    response_model=TimetableResponse,
    summary="Get room x slot timetable grid (same shape as public timetable)",
)
def get_coordinator_timetable_route(
    date: date = Query(..., description="Target date (YYYY-MM-DD)"),
    block_id: Optional[int] = Query(None, description="Optional block ID filter"),
    current_user: User = Depends(require_roles(UserRole.COORDINATOR)),
    db: Session = Depends(get_db),
):
    return get_coordinator_timetable(
        db=db,
        user=current_user,
        target_date=date,
        block_id=block_id,
    )


@router.get(
    "/bookings/export-csv",
    summary="Export bookings CSV for assigned blocks",
)
@router.get(
    "/export-csv",
    summary="Export bookings CSV for assigned blocks",
)
def export_coordinator_bookings_csv_route(
    date_from: Optional[date] = Query(None, description="Start date filter"),
    date_to: Optional[date] = Query(None, description="End date filter"),
    block_id: Optional[int] = Query(None, description="Block filter"),
    room_id: Optional[int] = Query(None, description="Room filter"),
    status: Optional[BookingStatus] = Query(None, description="Status filter"),
    search: Optional[str] = Query(None, description="Search keyword"),
    current_user: User = Depends(require_roles(UserRole.COORDINATOR)),
    db: Session = Depends(get_db),
):
    csv_data = export_coordinator_bookings_csv(
        db=db,
        user=current_user,
        date_from=date_from,
        date_to=date_to,
        block_id=block_id,
        room_id=room_id,
        status=status,
        search=search,
    )
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=coordinator_bookings_export.csv",
        },
    )


