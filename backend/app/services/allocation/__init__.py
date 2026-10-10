import time
from datetime import date, datetime
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session

from app.models.allocation import AllocationHistory
from app.models.booking import Booking
from app.models.enums import BookingStatus, RequesterType, RoomStatus, RoomType
from app.schemas.allocation import (
    AllocationApplyResponse,
    AllocationAssignment,
    AllocationComparison,
    AllocationMetricsResponse,
    AllocationRequestItem,
    AllocationSimulateResponse,
    AllocationWeightsConfig,
    SimulationResult,
)
from app.services.allocation.config import AllocationWeights
from app.services.allocation.models import (
    Assignment,
    RequestItem,
    RoomCandidate,
    booking_to_request_item,
    load_room_candidates,
    load_unavailable_slots,
)
from app.services.allocation.baseline import baseline_allocate
from app.services.allocation.optimizer import optimize_allocate
from app.models.room import Room
from app.models.time_slot import TimeSlot
from app.services.allocation.metrics import (
    compute_allocation_metrics,
    compute_utilization_heatmap,
    compute_wastage_distribution,
    EFFICIENCY_WEIGHTS,
)
from app.services.allocation.demo import generate_demo_allocation_requests
from app.services.allocation.reallocation import handle_room_unavailability


def assignment_to_schema(a: Assignment) -> AllocationAssignment:
    req_date = a.request.date
    if isinstance(req_date, str):
        req_date = date.fromisoformat(req_date[:10])

    cost_val = None
    if a.allocated and a.cost is not None:
        try:
            f_cost = float(a.cost)
            import math
            if not (math.isnan(f_cost) or math.isinf(f_cost)):
                cost_val = round(f_cost, 2)
        except (ValueError, TypeError):
            cost_val = None

    req_id = a.request.id
    if hasattr(req_id, "item"):
        req_id = req_id.item()

    return AllocationAssignment(
        request_id=str(req_id) if isinstance(req_id, str) else int(req_id),
        date=req_date,
        slot_id=int(a.request.slot_id),
        expected_strength=int(a.request.expected_strength),
        allocated=bool(a.allocated),
        room_id=int(a.room.id) if a.room else None,
        room_name=str(a.room.name) if a.room else None,
        block_id=int(a.room.block_id) if a.room and a.room.block_id is not None else None,
        block_name=str(a.room.block_name) if a.room and a.room.block_name else None,
        floor=int(a.room.floor) if a.room and a.room.floor is not None else None,
        capacity=int(a.room.capacity) if a.room and a.room.capacity is not None else None,
        reason_if_unallocated=a.reason_if_unallocated,
        cost=cost_val,
    )


def simulate_allocations(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    use_existing_bookings: bool = True,
    generate_demo: bool = False,
    demo_count: int = 25,
    custom_requests: Optional[List[AllocationRequestItem]] = None,
    weights_config: Optional[AllocationWeightsConfig] = None,
    record_history: bool = True,
) -> AllocationSimulateResponse:
    """
    Executes baseline and optimizer simulation side-by-side on either existing bookings or custom batch requests.
    Calculates detailed comparison metrics, heatmap matrix, wastage distribution, and stores run history.
    """
    start_time = time.time()
    if start_date is None:
        start_date = date.today()
    if end_date is None:
        end_date = start_date

    weights = (
        AllocationWeights.from_dict(weights_config.model_dump())
        if weights_config
        else AllocationWeights()
    )

    requests: List[RequestItem] = []
    excluded_booking_ids: Set[int] = set()

    # 1. Load requests
    if use_existing_bookings:
        active_statuses = [
            BookingStatus.PENDING,
            BookingStatus.COORDINATOR_APPROVED,
            BookingStatus.APPROVED,
        ]
        db_bookings = (
            db.query(Booking)
            .filter(
                Booking.date >= start_date,
                Booking.date <= end_date,
                Booking.status.in_(active_statuses),
            )
            .all()
        )
        for b in db_bookings:
            requests.append(booking_to_request_item(b))
            excluded_booking_ids.add(b.id)

    # 1b. If demo requested or requested non-existing without custom
    if generate_demo or (not use_existing_bookings and not custom_requests):
        demo_items = generate_demo_allocation_requests(
            db, count=demo_count, start_date=start_date, end_date=end_date
        )
        for idx, cr in enumerate(demo_items):
            r_id = cr.id if cr.id is not None else f"demo_{idx + 1}"
            requests.append(
                RequestItem(
                    id=r_id,
                    date=cr.date,
                    slot_id=cr.slot_id,
                    expected_strength=cr.expected_strength,
                    room_type=cr.room_type or RoomType.CLASSROOM,
                    required_facilities=cr.required_facilities,
                    department_id=cr.department_id,
                    preferred_block_id=cr.preferred_block_id,
                    preferred_floor=cr.preferred_floor,
                    created_at=cr.created_at,
                    requester_id=cr.roll_no or cr.email or str(r_id),
                    name=cr.name,
                    email=cr.email,
                    purpose=cr.purpose,
                )
            )

    if custom_requests:
        for idx, cr in enumerate(custom_requests):
            r_id = cr.id if cr.id is not None else f"custom_{idx + 1}"
            requests.append(
                RequestItem(
                    id=r_id,
                    date=cr.date,
                    slot_id=cr.slot_id,
                    expected_strength=cr.expected_strength,
                    room_type=cr.room_type or RoomType.CLASSROOM,
                    required_facilities=cr.required_facilities,
                    department_id=cr.department_id,
                    preferred_block_id=cr.preferred_block_id,
                    preferred_floor=cr.preferred_floor,
                    created_at=cr.created_at,
                    requester_id=cr.roll_no or cr.email or str(r_id),
                    name=cr.name,
                    email=cr.email,
                    purpose=cr.purpose,
                )
            )

    # 2. Load rooms and unavailable constraints
    rooms = load_room_candidates(db)
    unavailable_slots = load_unavailable_slots(
        db, start_date, end_date, exclude_booking_ids=excluded_booking_ids
    )

    # 3. Run Baseline
    baseline_assignments = baseline_allocate(requests, rooms, unavailable_slots)
    baseline_metrics = compute_allocation_metrics(baseline_assignments, unavailable_slots)

    # 4. Run Optimizer
    optimized_assignments = optimize_allocate(requests, rooms, unavailable_slots, weights)
    optimized_metrics = compute_allocation_metrics(optimized_assignments, unavailable_slots)

    # 5. Build comparison deltas
    eff_delta = round(optimized_metrics.efficiency_score - baseline_metrics.efficiency_score, 2)
    seat_delta = round(optimized_metrics.seat_utilization_pct - baseline_metrics.seat_utilization_pct, 2)
    wastage_red = round(baseline_metrics.average_wastage_pct - optimized_metrics.average_wastage_pct, 2)
    fac_delta = round(optimized_metrics.facility_match_pct - baseline_metrics.facility_match_pct, 2)
    pref_delta = round(optimized_metrics.preference_satisfaction_pct - baseline_metrics.preference_satisfaction_pct, 2)
    unallocated_delta = optimized_metrics.unallocated_count - baseline_metrics.unallocated_count

    comparison = AllocationComparison(
        efficiency_score_delta=eff_delta,
        seat_utilization_delta_pct=seat_delta,
        average_wastage_reduction_pct=wastage_red,
        facility_match_delta_pct=fac_delta,
        preference_satisfaction_delta_pct=pref_delta,
        unallocated_delta=unallocated_delta,
    )

    elapsed_ms = round((time.time() - start_time) * 1000.0, 2)

    # 6. Record history in DB
    if record_history and len(requests) > 0:
        try:
            history_entry = AllocationHistory(
                status="SIMULATED",
                date_from=start_date,
                date_to=end_date,
                total_requests=len(requests),
                baseline_metrics=baseline_metrics.model_dump(),
                optimized_metrics=optimized_metrics.model_dump(),
                execution_time_ms=elapsed_ms,
            )
            db.add(history_entry)
            db.commit()
        except Exception:
            db.rollback()

    # 7. Heatmap matrix, wastage distribution & maintenance rooms
    slots = db.query(TimeSlot).order_by(TimeSlot.order).all()
    wastage_dist = compute_wastage_distribution(baseline_assignments, optimized_assignments)
    heatmap_matrix = compute_utilization_heatmap(baseline_assignments, optimized_assignments, rooms, slots)

    maint_rooms_models = db.query(Room).filter(Room.status == RoomStatus.MAINTENANCE).all()
    maint_rooms_list = []
    for mr in maint_rooms_models:
        aff_cnt = (
            db.query(Booking)
            .filter(
                Booking.room_id == mr.id,
                Booking.date >= start_date,
                Booking.status.in_([
                    BookingStatus.PENDING,
                    BookingStatus.COORDINATOR_APPROVED,
                    BookingStatus.APPROVED,
                ]),
            )
            .count()
        )
        maint_rooms_list.append({
            "id": mr.id,
            "name": mr.name,
            "block_id": mr.block_id,
            "block_name": mr.block.name if mr.block else f"Block {mr.block_id}",
            "floor": mr.floor,
            "capacity": mr.capacity,
            "room_type": mr.room_type.value if hasattr(mr.room_type, "value") else str(mr.room_type),
            "maintenance_note": mr.maintenance_note or "Under scheduled maintenance",
            "affected_future_bookings": aff_cnt,
        })

    return AllocationSimulateResponse(
        date_range={"start_date": str(start_date), "end_date": str(end_date)},
        total_requests=len(requests),
        baseline=SimulationResult(
            allocations=[assignment_to_schema(a) for a in baseline_assignments],
            metrics=baseline_metrics,
        ),
        optimized=SimulationResult(
            allocations=[assignment_to_schema(a) for a in optimized_assignments],
            metrics=optimized_metrics,
        ),
        comparison=comparison,
        wastage_distribution=wastage_dist,
        heatmap_matrix=heatmap_matrix,
        maintenance_rooms=maint_rooms_list,
    )


def apply_allocations(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    use_existing_bookings: bool = True,
    custom_requests: Optional[List[AllocationRequestItem]] = None,
    weights_config: Optional[AllocationWeightsConfig] = None,
) -> AllocationApplyResponse:
    """
    Solves smart allocation with the optimizer and applies the assignments to the database.
    Updates existing bookings with optimal room assignments or creates new confirmed bookings.
    """
    start_time = time.time()
    if start_date is None:
        start_date = date.today()
    if end_date is None:
        end_date = start_date

    weights = (
        AllocationWeights.from_dict(weights_config.model_dump())
        if weights_config
        else AllocationWeights()
    )

    requests: List[RequestItem] = []
    excluded_booking_ids: Set[int] = set()

    if use_existing_bookings:
        active_statuses = [
            BookingStatus.PENDING,
            BookingStatus.COORDINATOR_APPROVED,
            BookingStatus.APPROVED,
        ]
        db_bookings = (
            db.query(Booking)
            .filter(
                Booking.date >= start_date,
                Booking.date <= end_date,
                Booking.status.in_(active_statuses),
            )
            .all()
        )
        for b in db_bookings:
            requests.append(booking_to_request_item(b))
            excluded_booking_ids.add(b.id)

    if custom_requests:
        for idx, cr in enumerate(custom_requests):
            r_id = cr.id if cr.id is not None else f"custom_{idx + 1}"
            requests.append(
                RequestItem(
                    id=r_id,
                    date=cr.date,
                    slot_id=cr.slot_id,
                    expected_strength=cr.expected_strength,
                    room_type=cr.room_type or RoomType.CLASSROOM,
                    required_facilities=cr.required_facilities,
                    department_id=cr.department_id,
                    preferred_block_id=cr.preferred_block_id,
                    preferred_floor=cr.preferred_floor,
                    created_at=cr.created_at,
                    requester_id=cr.roll_no or cr.email or str(r_id),
                    name=cr.name,
                    email=cr.email,
                    purpose=cr.purpose,
                )
            )

    rooms = load_room_candidates(db)
    unavailable_slots = load_unavailable_slots(
        db, start_date, end_date, exclude_booking_ids=excluded_booking_ids
    )

    # Run optimizer
    optimized_assignments = optimize_allocate(requests, rooms, unavailable_slots, weights)
    optimized_metrics = compute_allocation_metrics(optimized_assignments, unavailable_slots)

    import uuid
    applied_count = 0

    # Apply to database
    for a in optimized_assignments:
        if a.allocated and a.room:
            if a.request.booking_id:
                # Update existing booking
                bk = db.query(Booking).filter(Booking.id == a.request.booking_id).first()
                if bk:
                    bk.room_id = a.room.id
                    bk.decision_note = f"Allocated by Smart Allocation Optimizer. Fit cost: {a.cost:.2f}"
                    applied_count += 1
            else:
                # Create new booking
                new_ref = f"OPT-{uuid.uuid4().hex[:8].upper()}"
                new_bk = Booking(
                    reference=new_ref,
                    room_id=a.room.id,
                    date=a.request.date,
                    slot_id=a.request.slot_id,
                    purpose=a.request.purpose or "Smart Allocation Optimizer Booking",
                    expected_strength=a.request.expected_strength,
                    required_facilities=a.request.required_facilities or [],
                    status=BookingStatus.APPROVED,
                    requester_type=RequesterType.STUDENT,
                    roll_no=a.request.requester_id,
                    name=a.request.name or "Allocated User",
                    department_id=a.request.department_id or (rooms[0].department_id if rooms else 1),
                    phone="9876543210",
                    email=a.request.email or "allocated@college.edu",
                    decision_note=f"Created via Smart Allocation Apply. Cost: {a.cost:.2f}",
                )
                db.add(new_bk)
                applied_count += 1

    elapsed_ms = round((time.time() - start_time) * 1000.0, 2)

    history_entry = AllocationHistory(
        status="APPLIED",
        date_from=start_date,
        date_to=end_date,
        total_requests=len(requests),
        baseline_metrics={},
        optimized_metrics=optimized_metrics.model_dump(),
        execution_time_ms=elapsed_ms,
    )
    db.add(history_entry)
    db.commit()

    return AllocationApplyResponse(
        status="SUCCESS",
        total_requests=len(requests),
        applied_count=applied_count,
        unallocated_count=optimized_metrics.unallocated_count,
        metrics=optimized_metrics,
        message=f"Successfully applied {applied_count} optimized allocations.",
    )


__all__ = [
    "AllocationWeights",
    "RoomCandidate",
    "RequestItem",
    "Assignment",
    "baseline_allocate",
    "optimize_allocate",
    "compute_allocation_metrics",
    "handle_room_unavailability",
    "simulate_allocations",
    "apply_allocations",
    "EFFICIENCY_WEIGHTS",
]

