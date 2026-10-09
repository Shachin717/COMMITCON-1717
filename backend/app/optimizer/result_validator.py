from typing import List, Dict, Tuple, Set
from app.optimizer.constraints import (
    SessionData,
    RoomData,
    TimeBlock,
    intervals_overlap,
    is_room_eligible_for_session,
)


class ResultValidationError(Exception):
    def __init__(self, message: str, violations: List[str]):
        super().__init__(message)
        self.violations = violations


class AllocationResultValidator:
    """
    Independent verification of any candidate solution against all hard constraints.
    Rejects any solution with even a single violation.
    """

    @staticmethod
    def validate(
        allocations: Dict[int, int],  # session_id -> room_id
        sessions: Dict[int, SessionData],
        rooms: Dict[int, RoomData],
        room_unavailabilities: Dict[int, List[TimeBlock]],  # room_id -> list of blocked blocks
        confirmed_bookings: Dict[int, List[TimeBlock]],      # room_id -> list of booked blocks
        published_allocations: Dict[int, List[Tuple[int, TimeBlock]]],  # room_id -> list of (session_id, block)
    ) -> List[str]:
        violations: List[str] = []

        # 1. Static eligibility checks for each assigned (session, room)
        for s_id, r_id in allocations.items():
            if s_id not in sessions:
                violations.append(f"Session {s_id} is not in session pool.")
                continue
            if r_id not in rooms:
                violations.append(f"Room {r_id} is not in room pool.")
                continue

            session = sessions[s_id]
            room = rooms[r_id]

            eligible, reason = is_room_eligible_for_session(room, session)
            if not eligible:
                violations.append(
                    f"Session {s_id} (dept={session.department_id}, students={session.student_count}) "
                    f"assigned to ineligible Room {r_id} ({room.name}): {reason}"
                )

            # Check overlap with maintenance periods
            s_start = session.start_datetime
            s_end = session.end_datetime
            if r_id in room_unavailabilities:
                for block in room_unavailabilities[r_id]:
                    if intervals_overlap(s_start, s_end, block.start_datetime, block.end_datetime):
                        violations.append(
                            f"Session {s_id} overlaps with maintenance period for Room {room.name} "
                            f"({block.start_datetime} to {block.end_datetime})."
                        )

            # Check overlap with confirmed bookings
            if r_id in confirmed_bookings:
                for block in confirmed_bookings[r_id]:
                    if intervals_overlap(s_start, s_end, block.start_datetime, block.end_datetime):
                        violations.append(
                            f"Session {s_id} overlaps with confirmed booking for Room {room.name} "
                            f"({block.start_datetime} to {block.end_datetime})."
                        )

            # Check overlap with already published allocations (not being reallocated)
            if r_id in published_allocations:
                for other_s_id, block in published_allocations[r_id]:
                    if other_s_id != s_id and intervals_overlap(s_start, s_end, block.start_datetime, block.end_datetime):
                        violations.append(
                            f"Session {s_id} overlaps with published allocation of Session {other_s_id} in Room {room.name}."
                        )

        # 2. Check room conflicts among allocated sessions
        # No two sessions assigned to the same room can have overlapping time intervals
        room_to_sessions: Dict[int, List[int]] = {}
        for s_id, r_id in allocations.items():
            room_to_sessions.setdefault(r_id, []).append(s_id)

        for r_id, s_ids in room_to_sessions.items():
            for i in range(len(s_ids)):
                for j in range(i + 1, len(s_ids)):
                    s1 = sessions[s_ids[i]]
                    s2 = sessions[s_ids[j]]
                    if intervals_overlap(s1.start_datetime, s1.end_datetime, s2.start_datetime, s2.end_datetime):
                        violations.append(
                            f"Room conflict: Room {rooms[r_id].name} assigned simultaneously to Session {s1.id} "
                            f"and Session {s2.id} during overlapping interval."
                        )

        # 3. Check class group conflicts
        # A class group cannot attend two overlapping sessions simultaneously
        group_to_sessions: Dict[int, List[int]] = {}
        for s_id in allocations.keys():
            sess = sessions[s_id]
            group_to_sessions.setdefault(sess.class_group_id, []).append(s_id)

        for g_id, s_ids in group_to_sessions.items():
            for i in range(len(s_ids)):
                for j in range(i + 1, len(s_ids)):
                    s1 = sessions[s_ids[i]]
                    s2 = sessions[s_ids[j]]
                    if intervals_overlap(s1.start_datetime, s1.end_datetime, s2.start_datetime, s2.end_datetime):
                        violations.append(
                            f"Class group conflict: ClassGroup {g_id} has overlapping allocated sessions "
                            f"{s1.id} and {s2.id}."
                        )

        return violations

