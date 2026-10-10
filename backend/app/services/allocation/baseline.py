from datetime import date, datetime
from typing import Dict, List, Optional, Set, Tuple

from app.models.enums import RoomStatus
from app.services.allocation.models import (
    Assignment,
    RequestItem,
    RoomCandidate,
)


def baseline_allocate(
    requests: List[RequestItem],
    rooms: List[RoomCandidate],
    unavailable_slots: Optional[Set[Tuple[int, date, int]]] = None,
) -> List[Assignment]:
    """
    Naive First-Fit Allocator.
    
    Rules:
    1. Process requests strictly in arrival order (created_at).
    2. Give the first free room whose capacity >= expected_strength.
    3. Completely ignores facilities and preferences (department, block, floor).
    4. Guarantees zero double-booking / scheduling conflicts.
    """
    if unavailable_slots is None:
        unavailable_slots = set()

    if not requests:
        return []

    # Sort requests strictly by arrival order (created_at)
    # Using str(r.id) as a secondary tie-breaker for deterministic stability
    sorted_requests = sorted(
        requests,
        key=lambda r: (r.created_at or datetime.min, str(r.id))
    )

    # Order rooms deterministically by room id
    sorted_rooms = sorted(rooms, key=lambda rm: rm.id)

    # Track dynamically allocated (room_id, date, slot_id) to prevent conflicts
    allocated_slots: Set[Tuple[int, date, int]] = set()
    assignments: List[Assignment] = []

    for req in sorted_requests:
        assigned_room: Optional[RoomCandidate] = None

        for room in sorted_rooms:
            # 1. Hard availability check
            if room.status != RoomStatus.ACTIVE:
                continue

            slot_key = (room.id, req.date, req.slot_id)
            if slot_key in unavailable_slots or slot_key in allocated_slots:
                continue

            # 2. First-fit capacity check (ignoring facilities and preferences)
            if room.capacity >= req.expected_strength:
                assigned_room = room
                allocated_slots.add(slot_key)
                break

        if assigned_room:
            assignments.append(
                Assignment(
                    request=req,
                    room=assigned_room,
                    allocated=True,
                    cost=0.0,
                    reason_if_unallocated=None,
                )
            )
        else:
            assignments.append(
                Assignment(
                    request=req,
                    room=None,
                    allocated=False,
                    cost=None,
                    reason_if_unallocated="No active room with sufficient capacity available for slot.",
                )
            )

    return assignments

