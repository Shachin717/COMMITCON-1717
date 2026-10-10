from collections import defaultdict
from datetime import date, datetime
from typing import Dict, List, Optional, Set, Tuple
import numpy as np
from scipy.optimize import linear_sum_assignment

from app.models.enums import RoomStatus
from app.services.allocation.config import AllocationWeights
from app.services.allocation.models import (
    Assignment,
    RequestItem,
    RoomCandidate,
)

INFEASIBLE_THRESHOLD = 1e5
INFEASIBLE_PENALTY = 1e6


def optimize_allocate(
    requests: List[RequestItem],
    rooms: List[RoomCandidate],
    unavailable_slots: Optional[Set[Tuple[int, date, int]]] = None,
    weights: Optional[AllocationWeights] = None,
) -> List[Assignment]:
    """
    Smart Bipartite Matching Allocator using scipy.optimize.linear_sum_assignment.
    
    Hard constraints (make a pair infeasible / cost INFEASIBLE_PENALTY = 1e6):
    - Room status must be ACTIVE (not MAINTENANCE)
    - Room capacity >= request expected strength
    - Required facilities must all be present in room
    - Room type must match requested room type
    - Room must not have RoomBlock, timetable clash, or prior reservation on that slot
    
    Soft costs (weighted sum):
    - Capacity wastage: empty seats ratio ((capacity - strength) / capacity)
    - Preferred department / lab ownership: lower cost when dept room matches requester dept
    - Preferred block: lower cost when room is in requester's home/preferred block
    - Floor/block distance: penalty proportional to floor difference
    - Penalty for splitting: consecutive bookings for the same group across different rooms/blocks
    """
    if unavailable_slots is None:
        unavailable_slots = set()
    if weights is None:
        weights = AllocationWeights()

    if not requests:
        return []

    # Group requests by (date, slot_id)
    slot_groups: Dict[Tuple[date, int], List[RequestItem]] = defaultdict(list)
    for req in requests:
        slot_groups[(req.date, req.slot_id)].append(req)

    # Sort slots chronologically to model continuity / split penalties
    sorted_slots = sorted(slot_groups.keys(), key=lambda s: (s[0], s[1]))

    # Track earlier room assignments per requester on each date
    requester_daily_room: Dict[Tuple[str, date], RoomCandidate] = {}
    assignments: List[Assignment] = []

    for slot_key in sorted_slots:
        target_date, target_slot = slot_key
        req_list = slot_groups[slot_key]
        if not req_list:
            continue

        # Filter candidate rooms that are ACTIVE and not blocked/clashing on this slot
        candidate_rooms = [
            rm for rm in rooms
            if rm.status == RoomStatus.ACTIVE
            and (rm.id, target_date, target_slot) not in unavailable_slots
        ]

        if not candidate_rooms:
            # No available rooms for this slot
            for req in req_list:
                assignments.append(
                    Assignment(
                        request=req,
                        room=None,
                        allocated=False,
                        cost=None,
                        reason_if_unallocated="No active rooms available in this time slot.",
                    )
                )
            continue

        num_requests = len(req_list)
        num_rooms = len(candidate_rooms)

        # Build cost matrix: shape (num_requests, num_rooms)
        # Using a large finite penalty (1e6) for infeasible pairs
        cost_matrix = np.full((num_requests, num_rooms), INFEASIBLE_PENALTY, dtype=np.float64)

        for i, req in enumerate(req_list):
            for j, room in enumerate(candidate_rooms):
                # ---------------- HARD CONSTRAINTS ----------------
                # 1. Capacity
                if room.capacity < req.expected_strength:
                    continue

                # 2. Room Type
                if req.room_type and room.room_type != req.room_type:
                    continue

                # 3. Facilities
                if not req.facilities_set.issubset(room.facilities_set):
                    continue

                # ---------------- SOFT COSTS ----------------
                # 1. Capacity wastage (empty seats ratio in [0, 1))
                room_cap = max(1, room.capacity)
                wastage_ratio = max(0.0, (room_cap - req.expected_strength) / room_cap)
                c_wastage = weights.wastage_weight * wastage_ratio

                # 2. Department / Lab ownership
                if room.department_id is not None:
                    if req.department_id is not None and room.department_id == req.department_id:
                        c_dept = 0.0
                    else:
                        c_dept = weights.dept_ownership_weight * 1.0
                else:
                    # General campus pool room
                    c_dept = weights.dept_ownership_weight * 0.2

                # 3. Preferred Block
                if req.preferred_block_id is not None:
                    if room.block_id == req.preferred_block_id:
                        c_block = 0.0
                    else:
                        c_block = weights.block_match_weight * 1.0
                else:
                    c_block = 0.0

                # 4. Floor Distance
                if req.preferred_floor is not None:
                    floor_diff = min(1.0, abs(room.floor - req.preferred_floor) / 4.0)
                    c_dist = weights.distance_weight * floor_diff
                else:
                    c_dist = 0.0

                # 5. Penalty for Splitting
                c_split = 0.0
                requester_key = (req.requester_id or str(req.id), req.date)
                if requester_key in requester_daily_room:
                    prev_room = requester_daily_room[requester_key]
                    if prev_room.id == room.id:
                        c_split = 0.0  # Exact same room across consecutive slots
                    elif prev_room.block_id == room.block_id:
                        c_split = weights.split_penalty_weight * 0.3  # Same block
                    else:
                        c_split = weights.split_penalty_weight * 1.0  # Block change

                total_cost = c_wastage + c_dept + c_block + c_dist + c_split
                if np.isnan(total_cost) or np.isinf(total_cost):
                    total_cost = INFEASIBLE_PENALTY
                cost_matrix[i, j] = total_cost

        # Ensure no inf or NaN entries exist in the matrix
        cost_matrix = np.nan_to_num(
            cost_matrix,
            nan=INFEASIBLE_PENALTY,
            posinf=INFEASIBLE_PENALTY,
            neginf=INFEASIBLE_PENALTY,
        )

        # Solve assignment using Hungarian algorithm / Kuhn-Munkres
        # Supports non-square matrices of shape (num_requests, num_rooms)
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        assigned_req_indices = set()
        for r_idx, c_idx in zip(row_ind, col_ind):
            cost_val = float(cost_matrix[r_idx, c_idx])
            # Any assignment with cost >= INFEASIBLE_THRESHOLD is treated as unallocated
            if cost_val < INFEASIBLE_THRESHOLD:
                # Valid optimal assignment
                req = req_list[r_idx]
                room = candidate_rooms[c_idx]
                assigned_req_indices.add(r_idx)

                # Record continuity
                requester_key = (req.requester_id or str(req.id), req.date)
                requester_daily_room[requester_key] = room

                assignments.append(
                    Assignment(
                        request=req,
                        room=room,
                        allocated=True,
                        cost=round(cost_val, 2),
                        reason_if_unallocated=None,
                    )
                )

        # Record remaining unallocated requests
        for r_idx, req in enumerate(req_list):
            if r_idx not in assigned_req_indices:
                assignments.append(
                    Assignment(
                        request=req,
                        room=None,
                        allocated=False,
                        cost=None,
                        reason_if_unallocated="No feasible room satisfies hard constraints or capacity in this slot.",
                    )
                )

    return assignments

