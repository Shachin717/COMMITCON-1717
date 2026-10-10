import math
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from datetime import date
from app.api.deps import require_roles
from app.core.database import get_db
from app.models.allocation import AllocationHistory
from app.models.booking import Booking
from app.models.enums import BookingStatus, RoomStatus, UserRole
from app.models.room import Room
from app.models.user import User
from app.schemas.allocation import (
    AllocationApplyRequest,
    AllocationApplyResponse,
    AllocationHistoryItem,
    AllocationRequestItem,
    AllocationSimulateRequest,
    AllocationSimulateResponse,
    ReallocationRequest,
    ReallocationResponse,
)
from app.schemas.common import PaginatedResponse
from app.services.allocation import (
    apply_allocations,
    handle_room_unavailability,
    simulate_allocations,
)
from app.services.allocation.demo import generate_demo_allocation_requests

router = APIRouter(tags=["Allocation"])


@router.post(
    "/simulate",
    response_model=AllocationSimulateResponse,
    summary="Simulate baseline vs optimized allocations side-by-side with metrics",
)
def simulate_allocation_endpoint(
    payload: AllocationSimulateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.COORDINATOR)),
):
    """
    Run side-by-side allocation simulation:
    - Baseline (naive first-fit, capacity >= strength)
    - Optimized (scipy Hungarian linear sum assignment on hard & soft costs)
    Returns side-by-side allocation mappings, metrics, and improvement deltas.
    """
    try:
        return simulate_allocations(
            db=db,
            start_date=payload.start_date,
            end_date=payload.end_date,
            use_existing_bookings=payload.use_existing_bookings,
            generate_demo=payload.generate_demo,
            demo_count=payload.demo_count,
            custom_requests=payload.requests,
            weights_config=payload.weights,
            record_history=True,
        )
    except Exception as ex:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation error: {str(ex)}",
        )


@router.post(
    "/apply",
    response_model=AllocationApplyResponse,
    summary="Apply optimized room allocations to the database",
)
def apply_allocation_endpoint(
    payload: AllocationApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.COORDINATOR)),
):
    """
    Solves smart allocation with the optimizer and applies the results directly to the database:
    - Updates room assignment for existing bookings
    - Creates confirmed bookings for custom batch items
    """
    try:
        return apply_allocations(
            db=db,
            start_date=payload.start_date,
            end_date=payload.end_date,
            use_existing_bookings=payload.use_existing_bookings,
            custom_requests=payload.requests,
            weights_config=payload.weights,
        )
    except Exception as ex:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Allocation application error: {str(ex)}",
        )


@router.get(
    "/metrics/history",
    response_model=PaginatedResponse[AllocationHistoryItem],
    summary="Get historical simulation and allocation metrics runs",
)
def get_metrics_history_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.COORDINATOR)),
):
    """
    Retrieve historical log of allocation runs, including baseline vs optimized metrics.
    """
    query = db.query(AllocationHistory).order_by(AllocationHistory.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    pages = math.ceil(total / page_size) if total > 0 else 1

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post(
    "/reallocate",
    response_model=ReallocationResponse,
    summary="Trigger automatic relocation when a room goes into maintenance or exam block",
)
def reallocate_room_endpoint(
    payload: ReallocationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.COORDINATOR)),
):
    """
    When a room is marked MAINTENANCE or gets an EXAM block:
    - Computes minimal-disruption replacements for affected future bookings
    - Marks old bookings RELOCATED
    - Dispatches email notifications to requesters
    """
    try:
        return handle_room_unavailability(
            db=db,
            room_id=payload.room_id,
            reason=payload.reason,
            start_date=payload.start_date,
            end_date=payload.end_date,
            slot_id=payload.slot_id,
            send_notifications=payload.send_notifications,
            preview_only=payload.preview_only,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as ex:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reallocation error: {str(ex)}",
        )


@router.get(
    "/demo-requests",
    response_model=List[AllocationRequestItem],
    summary="Generate realistic batch of demo allocation requests for simulation",
)
def get_demo_requests_endpoint(
    count: int = Query(25, ge=1, le=200, description="Number of demo requests to generate"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.COORDINATOR)),
):
    """
    Generates a realistic set of academic demo requests mapped to active departments and blocks.
    """
    return generate_demo_allocation_requests(
        db=db,
        count=count,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/maintenance-rooms",
    summary="List all rooms currently in maintenance status with affected booking count",
)
def get_maintenance_rooms_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.COORDINATOR)),
):
    """
    Returns rooms currently flagged with MAINTENANCE status and their active booking counts.
    """
    today = date.today()
    maint_rooms = db.query(Room).filter(Room.status == RoomStatus.MAINTENANCE).all()
    results = []
    for r in maint_rooms:
        aff_cnt = (
            db.query(Booking)
            .filter(
                Booking.room_id == r.id,
                Booking.date >= today,
                Booking.status.in_([
                    BookingStatus.PENDING,
                    BookingStatus.COORDINATOR_APPROVED,
                    BookingStatus.APPROVED,
                ]),
            )
            .count()
        )
        results.append({
            "id": r.id,
            "name": r.name,
            "block_id": r.block_id,
            "block_name": r.block.name if r.block else f"Block {r.block_id}",
            "floor": r.floor,
            "capacity": r.capacity,
            "room_type": r.room_type.value if hasattr(r.room_type, "value") else str(r.room_type),
            "maintenance_note": r.maintenance_note or "Under maintenance",
            "affected_future_bookings": aff_cnt,
        })
    return {"rooms": results, "total": len(results)}


