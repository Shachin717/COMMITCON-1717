from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

from app.schemas.allocation import AllocationMetricsResponse
from app.services.allocation.models import Assignment, RoomCandidate

# Documented component weights for combined Efficiency Score (sum = 100%)
EFFICIENCY_WEIGHTS: Dict[str, float] = {
    "allocation_rate_weight": 0.25,        # 25% weight: Successfully servicing submitted requests
    "seat_utilization_weight": 0.30,       # 30% weight: High seat occupancy & minimizing room space wastage
    "facility_match_weight": 0.20,         # 20% weight: Satisfying requested multimedia / lab amenities
    "preference_satisfaction_weight": 0.15,# 15% weight: Fulfilling department ownership & location preferences
    "block_consistency_weight": 0.10,      # 10% weight: Minimizing physical transitions across blocks
}


def compute_allocation_metrics(
    assignments: List[Assignment],
    unavailable_slots: Optional[Set[Tuple[int, date, int]]] = None,
) -> AllocationMetricsResponse:
    """
    Computes comprehensive efficiency metrics for an allocation plan:
    - total_requests, allocated_count, unallocated_count
    - seat_utilization_pct (sum strength / sum capacity)
    - average_wastage_pct (average empty seats ratio)
    - facility_match_pct (percentage of requested amenities fulfilled)
    - preference_satisfaction_pct (department, block, and floor soft preferences)
    - conflict_count (double bookings, overcapacity, or clashing slots - MUST BE 0)
    - block_switch_count (physical block movements between slots or away from home block)
    - efficiency_score (0 - 100 composite index weighted across key dimensions)
    """
    total_requests = len(assignments)
    allocated_items = [a for a in assignments if a.allocated and a.room is not None]
    allocated_count = len(allocated_items)
    unallocated_count = total_requests - allocated_count

    if total_requests == 0:
        return AllocationMetricsResponse(
            total_requests=0,
            allocated_count=0,
            unallocated_count=0,
            allocation_rate_pct=0.0,
            seat_utilization_pct=0.0,
            average_wastage_pct=0.0,
            facility_match_pct=0.0,
            preference_satisfaction_pct=0.0,
            conflict_count=0,
            block_switch_count=0,
            efficiency_score=0.0,
            weights_breakdown=EFFICIENCY_WEIGHTS,
        )

    # 1. Allocation Rate %
    allocation_rate_pct = (
        (allocated_count / total_requests * 100.0) if total_requests > 0 else 0.0
    )

    # 2. Seat Utilization % and Average Wastage %
    if allocated_items:
        total_strength = sum(a.request.expected_strength for a in allocated_items)
        total_capacity = sum(a.room.capacity for a in allocated_items if a.room)
        seat_utilization_pct = (
            (total_strength / total_capacity * 100.0) if total_capacity > 0 else 0.0
        )
        wastages = [
            ((max(1, a.room.capacity) - a.request.expected_strength) / max(1, a.room.capacity) * 100.0)
            for a in allocated_items if a.room
        ]
        average_wastage_pct = (sum(wastages) / len(wastages)) if wastages else 0.0
    else:
        seat_utilization_pct = 0.0
        average_wastage_pct = 0.0

    # 3. Facility Match %
    if allocated_items:
        facility_scores: List[float] = []
        for a in allocated_items:
            req_fac = a.request.facilities_set
            if not req_fac:
                facility_scores.append(100.0)
            elif a.room:
                matched = len(req_fac & a.room.facilities_set)
                facility_scores.append((matched / len(req_fac)) * 100.0)
            else:
                facility_scores.append(0.0)
        facility_match_pct = (sum(facility_scores) / len(facility_scores)) if facility_scores else 0.0
    else:
        facility_match_pct = 0.0

    # 4. Preference Satisfaction %
    if allocated_items:
        pref_scores: List[float] = []
        for a in allocated_items:
            req = a.request
            room = a.room
            if not room:
                continue
            item_scores: List[float] = []

            # Department ownership
            if room.department_id is not None:
                if req.department_id is not None and room.department_id == req.department_id:
                    item_scores.append(100.0)
                else:
                    item_scores.append(0.0)
            else:
                item_scores.append(80.0)

            # Block match
            if req.preferred_block_id is not None:
                if room.block_id == req.preferred_block_id:
                    item_scores.append(100.0)
                else:
                    item_scores.append(0.0)
            else:
                item_scores.append(100.0)

            # Floor match
            if req.preferred_floor is not None:
                floor_dist = abs(room.floor - req.preferred_floor)
                item_scores.append(max(0.0, 100.0 - (floor_dist * 25.0)))
            else:
                item_scores.append(100.0)

            pref_scores.append(sum(item_scores) / len(item_scores))
        preference_satisfaction_pct = (sum(pref_scores) / len(pref_scores)) if pref_scores else 0.0
    else:
        preference_satisfaction_pct = 0.0

    # 5. Conflict Count (MUST BE 0)
    conflict_count = 0
    assigned_slots: Dict[Tuple[int, date, int], int] = defaultdict(int)

    for a in allocated_items:
        if not a.room:
            continue
        slot_key = (a.room.id, a.request.date, a.request.slot_id)
        assigned_slots[slot_key] += 1

        # Double booking check
        if assigned_slots[slot_key] > 1:
            conflict_count += 1

        # Hard capacity violation check
        if a.room.capacity < a.request.expected_strength:
            conflict_count += 1

        # Blocked / timetable conflict check
        if unavailable_slots and slot_key in unavailable_slots:
            conflict_count += 1

    # 6. Block-switch count
    block_switch_count = 0
    requester_schedule: Dict[Tuple[str, date], List[Assignment]] = defaultdict(list)
    for a in allocated_items:
        req_key = (a.request.requester_id or str(a.request.id), a.request.date)
        requester_schedule[req_key].append(a)

    for req_key, user_assignments in requester_schedule.items():
        user_assignments.sort(key=lambda item: item.request.slot_id)
        for i in range(1, len(user_assignments)):
            prev_alloc = user_assignments[i - 1]
            curr_alloc = user_assignments[i]
            # If consecutive slots (e.g. slot 2 and slot 3), switching blocks is disruptive
            if prev_alloc.room and curr_alloc.room and curr_alloc.request.slot_id == prev_alloc.request.slot_id + 1:
                if curr_alloc.room.block_id != prev_alloc.room.block_id:
                    block_switch_count += 1

    # Also count placements away from preferred home block
    for a in allocated_items:
        if a.room and a.request.preferred_block_id is not None and a.room.block_id != a.request.preferred_block_id:
            block_switch_count += 1

    # 7. Combined Efficiency Score (0 - 100)
    # Severe penalty: if conflict_count > 0, system integrity is violated -> score = 0.0
    if conflict_count > 0 or total_requests == 0:
        efficiency_score = 0.0
    else:
        # Block consistency metric (100 = 0 switches)
        switch_ratio = block_switch_count / max(1, allocated_count)
        block_consistency_score = max(0.0, 100.0 - (switch_ratio * 100.0))

        score = (
            EFFICIENCY_WEIGHTS["allocation_rate_weight"] * allocation_rate_pct
            + EFFICIENCY_WEIGHTS["seat_utilization_weight"] * seat_utilization_pct
            + EFFICIENCY_WEIGHTS["facility_match_weight"] * facility_match_pct
            + EFFICIENCY_WEIGHTS["preference_satisfaction_weight"] * preference_satisfaction_pct
            + EFFICIENCY_WEIGHTS["block_consistency_weight"] * block_consistency_score
        )
        efficiency_score = max(0.0, min(100.0, score))

    return AllocationMetricsResponse(
        total_requests=total_requests,
        allocated_count=allocated_count,
        unallocated_count=unallocated_count,
        allocation_rate_pct=round(allocation_rate_pct, 2),
        seat_utilization_pct=round(seat_utilization_pct, 2),
        average_wastage_pct=round(average_wastage_pct, 2),
        facility_match_pct=round(facility_match_pct, 2),
        preference_satisfaction_pct=round(preference_satisfaction_pct, 2),
        conflict_count=conflict_count,
        block_switch_count=block_switch_count,
        efficiency_score=round(efficiency_score, 2),
        weights_breakdown=EFFICIENCY_WEIGHTS,
    )


def compute_wastage_distribution(
    baseline_assignments: List[Assignment],
    optimized_assignments: List[Assignment],
) -> List[Dict[str, Any]]:
    """
    Computes distribution of room capacity wastage across standard buckets for
    Baseline vs Optimized allocations.
    """
    buckets = [
        {"bin": "0-10%", "label": "0 - 10% (Optimal)", "min": 0.0, "max": 10.0, "baseline": 0, "optimized": 0},
        {"bin": "10-25%", "label": "10 - 25% (Good Fit)", "min": 10.0, "max": 25.0, "baseline": 0, "optimized": 0},
        {"bin": "25-40%", "label": "25 - 40% (Moderate)", "min": 25.0, "max": 40.0, "baseline": 0, "optimized": 0},
        {"bin": "40-60%", "label": "40 - 60% (Excessive)", "min": 40.0, "max": 60.0, "baseline": 0, "optimized": 0},
        {"bin": ">60%", "label": "> 60% (Severe)", "min": 60.0, "max": 1000.0, "baseline": 0, "optimized": 0},
    ]

    base_allocated = [a for a in baseline_assignments if a.allocated and a.room]
    opt_allocated = [a for a in optimized_assignments if a.allocated and a.room]

    for a in base_allocated:
        room_cap = max(1, a.room.capacity)
        wastage = max(0.0, ((room_cap - a.request.expected_strength) / room_cap) * 100.0)
        for b in buckets:
            if (b["min"] == 0.0 and wastage <= b["max"]) or (b["min"] < wastage <= b["max"]):
                b["baseline"] += 1
                break

    for a in opt_allocated:
        room_cap = max(1, a.room.capacity)
        wastage = max(0.0, ((room_cap - a.request.expected_strength) / room_cap) * 100.0)
        for b in buckets:
            if (b["min"] == 0.0 and wastage <= b["max"]) or (b["min"] < wastage <= b["max"]):
                b["optimized"] += 1
                break

    total_base = len(base_allocated)
    total_opt = len(opt_allocated)

    result = []
    for b in buckets:
        result.append({
            "bin": b["bin"],
            "label": b["label"],
            "baseline": b["baseline"],
            "optimized": b["optimized"],
            "baseline_pct": round((b["baseline"] / total_base) * 100.0, 1) if total_base > 0 else 0.0,
            "optimized_pct": round((b["optimized"] / total_opt) * 100.0, 1) if total_opt > 0 else 0.0,
        })

    return result


def compute_utilization_heatmap(
    baseline_assignments: List[Assignment],
    optimized_assignments: List[Assignment],
    rooms: List[RoomCandidate],
    slots: List[Any],
) -> List[Dict[str, Any]]:
    """
    Computes a room x period utilization matrix for baseline and optimized assignments.
    """
    if not rooms:
        return []

    base_map: Dict[Tuple[int, int], Assignment] = {
        (a.room.id, a.request.slot_id): a for a in baseline_assignments if a.allocated and a.room
    }
    opt_map: Dict[Tuple[int, int], Assignment] = {
        (a.room.id, a.request.slot_id): a for a in optimized_assignments if a.allocated and a.room
    }

    matrix: List[Dict[str, Any]] = []

    for r in rooms:
        row_slots = []
        room_cap = max(1, r.capacity)
        for s in slots:
            slot_id = s.id if hasattr(s, "id") else s["id"]
            slot_label = s.label if hasattr(s, "label") else s.get("label", f"Slot {slot_id}")
            start_str = str(s.start_time) if hasattr(s, "start_time") else str(s.get("start_time", ""))
            end_str = str(s.end_time) if hasattr(s, "end_time") else str(s.get("end_time", ""))

            base_a = base_map.get((r.id, slot_id))
            opt_a = opt_map.get((r.id, slot_id))

            cell_info = {
                "slot_id": slot_id,
                "slot_label": slot_label,
                "time_range": f"{start_str[:5]} - {end_str[:5]}" if start_str and end_str else slot_label,
                "baseline": {
                    "allocated": base_a is not None,
                    "strength": base_a.request.expected_strength if base_a else 0,
                    "utilization_pct": round((base_a.request.expected_strength / room_cap) * 100.0, 1) if base_a else 0.0,
                    "requester": base_a.request.name or base_a.request.requester_id if base_a else None,
                    "purpose": base_a.request.purpose if base_a else None,
                    "request_id": str(base_a.request.id) if base_a else None,
                },
                "optimized": {
                    "allocated": opt_a is not None,
                    "strength": opt_a.request.expected_strength if opt_a else 0,
                    "utilization_pct": round((opt_a.request.expected_strength / room_cap) * 100.0, 1) if opt_a else 0.0,
                    "requester": opt_a.request.name or opt_a.request.requester_id if opt_a else None,
                    "purpose": opt_a.request.purpose if opt_a else None,
                    "request_id": str(opt_a.request.id) if opt_a else None,
                },
            }
            row_slots.append(cell_info)

        matrix.append({
            "room_id": r.id,
            "room_name": r.name,
            "block_id": r.block_id,
            "block_name": r.block_name,
            "floor": r.floor,
            "capacity": r.capacity,
            "room_type": r.room_type.value if hasattr(r.room_type, "value") else str(r.room_type),
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "facilities": list(r.facilities) if isinstance(r.facilities, (list, set, tuple)) else [],
            "slots": row_slots,
        })

    return matrix


