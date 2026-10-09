import time
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from ortools.sat.python import cp_model

from app.optimizer.constraints import (
    SessionData,
    RoomData,
    TimeBlock,
    intervals_overlap,
    is_room_eligible_for_session,
)
from app.optimizer.objective import ObjectiveConfig
from app.optimizer.result_validator import AllocationResultValidator


@dataclass
class OptimizationSolverResult:
    status: str  # OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN, MODEL_INVALID, ERROR
    objective_value: Optional[float]
    solver_runtime_ms: float
    allocations: Dict[int, int] = field(default_factory=dict)  # session_id -> room_id
    unallocated_session_ids: List[int] = field(default_factory=list)
    is_optimal: bool = False
    is_feasible: bool = False
    error_message: Optional[str] = None


class OrToolsAllocationSolver:
    def __init__(
        self,
        time_limit_seconds: float = 30.0,
        random_seed: int = 42,
        num_workers: int = 4,
        objective_config: Optional[ObjectiveConfig] = None,
    ):
        self.time_limit_seconds = time_limit_seconds
        self.random_seed = random_seed
        self.num_workers = num_workers
        self.objective_config = objective_config or ObjectiveConfig()

    def solve(
        self,
        sessions: List[SessionData],
        rooms: List[RoomData],
        room_unavailabilities: Optional[Dict[int, List[TimeBlock]]] = None,
        confirmed_bookings: Optional[Dict[int, List[TimeBlock]]] = None,
        published_allocations: Optional[Dict[int, List[Tuple[int, TimeBlock]]]] = None,
        previous_allocations: Optional[Dict[int, int]] = None,  # session_id -> room_id
    ) -> OptimizationSolverResult:
        start_clock = time.perf_counter()

        room_unavail = room_unavailabilities or {}
        conf_bookings = confirmed_bookings or {}
        pub_allocs = published_allocations or {}
        prev_allocs = previous_allocations or {}

        session_map = {s.id: s for s in sessions}
        room_map = {r.id: r for r in rooms}

        if not sessions:
            elapsed_ms = (time.perf_counter() - start_clock) * 1000.0
            return OptimizationSolverResult(
                status="OPTIMAL",
                objective_value=0.0,
                solver_runtime_ms=elapsed_ms,
                allocations={},
                unallocated_session_ids=[],
                is_optimal=True,
                is_feasible=True,
            )

        model = cp_model.CpModel()

        # Decision variables: x[session_id, room_id]
        # Only created for strictly eligible combinations
        x: Dict[Tuple[int, int], cp_model.IntVar] = {}
        # Unallocated indicator variable for each session
        unallocated: Dict[int, cp_model.IntVar] = {}

        # 1. Variable creation with static & external hard constraint filtering
        for s in sessions:
            unallocated[s.id] = model.NewBoolVar(f"unallocated_{s.id}")
            for r in rooms:
                # Check eligibility
                eligible, _ = is_room_eligible_for_session(r, s)
                if not eligible:
                    continue

                # Check external maintenance conflict
                s_start, s_end = s.start_datetime, s.end_datetime
                if r.id in room_unavail:
                    if any(
                        intervals_overlap(s_start, s_end, b.start_datetime, b.end_datetime)
                        for b in room_unavail[r.id]
                    ):
                        continue

                # Check external confirmed bookings conflict
                if r.id in conf_bookings:
                    if any(
                        intervals_overlap(s_start, s_end, b.start_datetime, b.end_datetime)
                        for b in conf_bookings[r.id]
                    ):
                        continue

                # Check external published allocations conflict (for sessions not in our set)
                if r.id in pub_allocs:
                    if any(
                        other_sid != s.id
                        and intervals_overlap(s_start, s_end, b.start_datetime, b.end_datetime)
                        for other_sid, b in pub_allocs[r.id]
                    ):
                        continue

                x[(s.id, r.id)] = model.NewBoolVar(f"x_{s.id}_{r.id}")

        # 2. Hard Constraint: Each session gets at most one room, or is unallocated
        for s in sessions:
            assigned_rooms = [x[(s.id, r.id)] for r in rooms if (s.id, r.id) in x]
            model.Add(unallocated[s.id] + sum(assigned_rooms) == 1)

        # 3. Hard Constraint: Room cannot host overlapping sessions
        # For each room, examine pairs of sessions that overlap
        sessions_by_room: Dict[int, List[SessionData]] = {}
        for (s_id, r_id) in x.keys():
            sessions_by_room.setdefault(r_id, []).append(session_map[s_id])

        for r_id, room_sessions in sessions_by_room.items():
            num_sess = len(room_sessions)
            for i in range(num_sess):
                for j in range(i + 1, num_sess):
                    s1 = room_sessions[i]
                    s2 = room_sessions[j]
                    if intervals_overlap(s1.start_datetime, s1.end_datetime, s2.start_datetime, s2.end_datetime):
                        model.Add(x[(s1.id, r_id)] + x[(s2.id, r_id)] <= 1)

        # 4. Hard Constraint: Class group cannot attend two overlapping sessions
        # Group sessions by class_group_id
        sessions_by_group: Dict[int, List[SessionData]] = {}
        for s in sessions:
            sessions_by_group.setdefault(s.class_group_id, []).append(s)

        for g_id, group_sessions in sessions_by_group.items():
            num_sess = len(group_sessions)
            for i in range(num_sess):
                for j in range(i + 1, num_sess):
                    s1 = group_sessions[i]
                    s2 = group_sessions[j]
                    if intervals_overlap(s1.start_datetime, s1.end_datetime, s2.start_datetime, s2.end_datetime):
                        s1_vars = [x[(s1.id, r.id)] for r in rooms if (s1.id, r.id) in x]
                        s2_vars = [x[(s2.id, r.id)] for r in rooms if (s2.id, r.id) in x]
                        model.Add(sum(s1_vars) + sum(s2_vars) <= 1)

        # 5. Objective Function: Soft constraints & penalties
        objective_terms = []
        # Term 1: Penalty for unallocated sessions
        for s in sessions:
            objective_terms.append(unallocated[s.id] * self.objective_config.weight_unallocated)

        # Term 2: Soft penalty for assignment (unused seats, reallocation perturbation)
        for (s_id, r_id), var in x.items():
            s = session_map[s_id]
            r = room_map[r_id]
            cost = self.objective_config.calculate_assignment_cost(
                session=s,
                room=r,
                previous_room_id=prev_allocs.get(s_id),
            )
            if cost > 0:
                objective_terms.append(var * cost)

        model.Minimize(sum(objective_terms))

        # 6. Solver execution
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(self.time_limit_seconds)
        solver.parameters.random_seed = int(self.random_seed)
        solver.parameters.num_search_workers = int(self.num_workers)

        solver_status = solver.Solve(model)
        elapsed_ms = (time.perf_counter() - start_clock) * 1000.0

        status_str_map = {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.MODEL_INVALID: "MODEL_INVALID",
            cp_model.UNKNOWN: "UNKNOWN",
        }
        status_name = status_str_map.get(solver_status, "UNKNOWN")

        if solver_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            allocations: Dict[int, int] = {}
            unallocated_sids: List[int] = []

            for s in sessions:
                assigned = False
                for r in rooms:
                    if (s.id, r.id) in x and solver.Value(x[(s.id, r.id)]) == 1:
                        allocations[s.id] = r.id
                        assigned = True
                        break
                if not assigned:
                    unallocated_sids.append(s.id)

            # Independent validation of result
            violations = AllocationResultValidator.validate(
                allocations=allocations,
                sessions=session_map,
                rooms=room_map,
                room_unavailabilities=room_unavail,
                confirmed_bookings=conf_bookings,
                published_allocations=pub_allocs,
            )

            if violations:
                return OptimizationSolverResult(
                    status="ERROR",
                    objective_value=None,
                    solver_runtime_ms=elapsed_ms,
                    allocations={},
                    unallocated_session_ids=list(session_map.keys()),
                    is_optimal=False,
                    is_feasible=False,
                    error_message=f"Validation failed after solve: {'; '.join(violations[:5])}",
                )

            return OptimizationSolverResult(
                status=status_name,
                objective_value=solver.ObjectiveValue(),
                solver_runtime_ms=elapsed_ms,
                allocations=allocations,
                unallocated_session_ids=unallocated_sids,
                is_optimal=(solver_status == cp_model.OPTIMAL),
                is_feasible=True,
            )

        # Infeasible or error
        return OptimizationSolverResult(
            status=status_name,
            objective_value=None,
            solver_runtime_ms=elapsed_ms,
            allocations={},
            unallocated_session_ids=list(session_map.keys()),
            is_optimal=False,
            is_feasible=False,
            error_message=f"Solver stopped with status: {status_name}",
        )


class FirstFitBaselineSolver:
    """
    Greedy First-Fit Baseline Algorithm.
    Uses the exact same hard eligibility constraints to benchmark against CP-SAT.
    """

    def solve(
        self,
        sessions: List[SessionData],
        rooms: List[RoomData],
        room_unavailabilities: Optional[Dict[int, List[TimeBlock]]] = None,
        confirmed_bookings: Optional[Dict[int, List[TimeBlock]]] = None,
        published_allocations: Optional[Dict[int, List[Tuple[int, TimeBlock]]]] = None,
    ) -> OptimizationSolverResult:
        start_clock = time.perf_counter()

        room_unavail = room_unavailabilities or {}
        conf_bookings = confirmed_bookings or {}
        pub_allocs = published_allocations or {}

        session_map = {s.id: s for s in sessions}
        room_map = {r.id: r for r in rooms}

        # Sort sessions by date and start time
        sorted_sessions = sorted(sessions, key=lambda s: (s.session_date, s.start_time, -s.student_count))

        allocations: Dict[int, int] = {}
        unallocated_sids: List[int] = []

        # Keep track of assigned intervals per room during this run
        assigned_intervals_by_room: Dict[int, List[TimeBlock]] = {}

        for s in sorted_sessions:
            assigned = False
            s_start, s_end = s.start_datetime, s.end_datetime

            # Search rooms (sorted by capacity ascending for reasonable fit)
            candidate_rooms = sorted(rooms, key=lambda r: r.capacity)

            for r in candidate_rooms:
                eligible, _ = is_room_eligible_for_session(r, s)
                if not eligible:
                    continue

                # Maintenance check
                if r.id in room_unavail:
                    if any(
                        intervals_overlap(s_start, s_end, b.start_datetime, b.end_datetime)
                        for b in room_unavail[r.id]
                    ):
                        continue

                # Confirmed bookings check
                if r.id in conf_bookings:
                    if any(
                        intervals_overlap(s_start, s_end, b.start_datetime, b.end_datetime)
                        for b in conf_bookings[r.id]
                    ):
                        continue

                # Published allocations check
                if r.id in pub_allocs:
                    if any(
                        other_sid != s.id
                        and intervals_overlap(s_start, s_end, b.start_datetime, b.end_datetime)
                        for other_sid, b in pub_allocs[r.id]
                    ):
                        continue

                # Run-time overlapping assignments in this room
                if r.id in assigned_intervals_by_room:
                    if any(
                        intervals_overlap(s_start, s_end, b.start_datetime, b.end_datetime)
                        for b in assigned_intervals_by_room[r.id]
                    ):
                        continue

                # Found eligible room!
                allocations[s.id] = r.id
                assigned_intervals_by_room.setdefault(r.id, []).append(
                    TimeBlock(start_datetime=s_start, end_datetime=s_end)
                )
                assigned = True
                break

            if not assigned:
                unallocated_sids.append(s.id)

        elapsed_ms = (time.perf_counter() - start_clock) * 1000.0

        # Validate with independent validator
        violations = AllocationResultValidator.validate(
            allocations=allocations,
            sessions=session_map,
            rooms=room_map,
            room_unavailabilities=room_unavail,
            confirmed_bookings=conf_bookings,
            published_allocations=pub_allocs,
        )

        if violations:
            return OptimizationSolverResult(
                status="ERROR",
                objective_value=None,
                solver_runtime_ms=elapsed_ms,
                allocations={},
                unallocated_session_ids=list(session_map.keys()),
                is_optimal=False,
                is_feasible=False,
                error_message=f"Baseline produced invalid result: {'; '.join(violations[:5])}",
            )

        status_str = "FEASIBLE" if allocations else "INFEASIBLE"
        return OptimizationSolverResult(
            status=status_str,
            objective_value=float(len(unallocated_sids) * 100000),
            solver_runtime_ms=elapsed_ms,
            allocations=allocations,
            unallocated_session_ids=unallocated_sids,
            is_optimal=False,
            is_feasible=True,
        )

