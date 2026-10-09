from typing import Dict, Optional, Any
from app.core.config import settings
from app.optimizer.constraints import SessionData, RoomData


class ObjectiveConfig:
    def __init__(
        self,
        weight_unallocated: Optional[int] = None,
        weight_seat_waste: Optional[int] = None,
        weight_preference: Optional[int] = None,
        weight_reallocation_change: Optional[int] = None,
    ):
        self.weight_unallocated = (
            weight_unallocated
            if weight_unallocated is not None
            else settings.WEIGHT_UNALLOCATED_SESSION
        )
        self.weight_seat_waste = (
            weight_seat_waste
            if weight_seat_waste is not None
            else settings.WEIGHT_SEAT_WASTE
        )
        self.weight_preference = (
            weight_preference
            if weight_preference is not None
            else settings.WEIGHT_DEPARTMENT_PREFERENCE
        )
        self.weight_reallocation_change = (
            weight_reallocation_change
            if weight_reallocation_change is not None
            else settings.WEIGHT_REALLOCATION_CHANGE
        )

    def calculate_assignment_cost(
        self,
        session: SessionData,
        room: RoomData,
        previous_room_id: Optional[int] = None,
    ) -> int:
        """
        Calculates the soft penalty cost of assigning `session` to `room`.
        Lower is better.
        """
        cost = 0

        # 1. Unused seats penalty
        unused_seats = max(0, room.capacity - session.student_count)
        cost += unused_seats * self.weight_seat_waste

        # 2. Reallocation stability penalty: penalize changing previous assignment
        if previous_room_id is not None and previous_room_id != room.id:
            cost += self.weight_reallocation_change

        return cost

