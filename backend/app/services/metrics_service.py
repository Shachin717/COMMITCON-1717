from typing import List, Dict, Tuple, Optional
from app.optimizer.constraints import (
    SessionData,
    RoomData,
    TimeBlock,
    intervals_overlap,
)
from app.optimizer.solver import OptimizationSolverResult
from app.schemas.metrics import AlgorithmMetrics, BenchmarkComparisonResponse


class MetricsService:
    @staticmethod
    def calculate_metrics(
        algorithm_name: str,
        result: OptimizationSolverResult,
        sessions: List[SessionData],
        rooms: List[RoomData],
        previous_allocations: Optional[Dict[int, int]] = None,
    ) -> AlgorithmMetrics:
        session_map = {s.id: s for s in sessions}
        room_map = {r.id: r for r in rooms}
        total_eligible = len(sessions)
        allocated_count = len(result.allocations)
        unallocated_count = len(result.unallocated_session_ids)

        # 1. Allocation rate
        allocation_rate = (
            (allocated_count / total_eligible * 100.0) if total_eligible > 0 else 0.0
        )

        # 2. Seat utilization
        total_students_assigned = sum(
            session_map[sid].student_count
            for sid in result.allocations.keys()
            if sid in session_map
        )
        total_capacity_assigned = sum(
            room_map[rid].capacity
            for rid in result.allocations.values()
            if rid in room_map
        )
        seat_utilization = (
            (total_students_assigned / total_capacity_assigned * 100.0)
            if total_capacity_assigned > 0
            else 0.0
        )

        # 3. Room occupancy rate
        # Distinct rooms used / total active rooms * 100
        active_rooms_count = len([r for r in rooms if r.is_active])
        rooms_used = len(set(result.allocations.values()))
        room_occupancy = (
            (rooms_used / active_rooms_count * 100.0)
            if active_rooms_count > 0
            else 0.0
        )

        # 4. Room conflict count
        room_conflict_count = 0
        room_sessions: Dict[int, List[SessionData]] = {}
        for sid, rid in result.allocations.items():
            if sid in session_map:
                room_sessions.setdefault(rid, []).append(session_map[sid])
        for rid, r_sess in room_sessions.items():
            for i in range(len(r_sess)):
                for j in range(i + 1, len(r_sess)):
                    if intervals_overlap(
                        r_sess[i].start_datetime,
                        r_sess[i].end_datetime,
                        r_sess[j].start_datetime,
                        r_sess[j].end_datetime,
                    ):
                        room_conflict_count += 1

        # 5. Class schedule conflict count
        class_conflict_count = 0
        group_sessions: Dict[int, List[SessionData]] = {}
        for sid in result.allocations.keys():
            if sid in session_map:
                s = session_map[sid]
                group_sessions.setdefault(s.class_group_id, []).append(s)
        for gid, g_sess in group_sessions.items():
            for i in range(len(g_sess)):
                for j in range(i + 1, len(g_sess)):
                    if intervals_overlap(
                        g_sess[i].start_datetime,
                        g_sess[i].end_datetime,
                        g_sess[j].start_datetime,
                        g_sess[j].end_datetime,
                    ):
                        class_conflict_count += 1

        # 6. Preference satisfaction rate
        # Perfect satisfaction is when excess capacity is minimal (>= 75% efficiency)
        satisfied_count = 0
        for sid, rid in result.allocations.items():
            s = session_map.get(sid)
            r = room_map.get(rid)
            if s and r and r.capacity > 0:
                util = s.student_count / r.capacity
                if util >= 0.60:
                    satisfied_count += 1
        pref_rate = (
            (satisfied_count / allocated_count * 100.0)
            if allocated_count > 0
            else 100.0
        )

        # 7. Assignments changed
        assignments_changed = None
        if previous_allocations is not None:
            changed = 0
            for sid, rid in result.allocations.items():
                prev_r = previous_allocations.get(sid)
                if prev_r is not None and prev_r != rid:
                    changed += 1
            assignments_changed = changed

        return AlgorithmMetrics(
            algorithm_name=algorithm_name,
            allocation_rate=round(allocation_rate, 2),
            seat_utilization=round(seat_utilization, 2),
            room_occupancy_rate=round(room_occupancy, 2),
            room_conflict_count=room_conflict_count,
            class_conflict_count=class_conflict_count,
            preference_satisfaction_rate=round(pref_rate, 2),
            runtime_ms=round(result.solver_runtime_ms, 2),
            allocated_sessions=allocated_count,
            unallocated_sessions=unallocated_count,
            total_eligible_sessions=total_eligible,
            assignments_changed=assignments_changed,
        )

    @classmethod
    def compare_benchmark(
        cls,
        run_id: int,
        optimizer_res: OptimizationSolverResult,
        baseline_res: OptimizationSolverResult,
        sessions: List[SessionData],
        rooms: List[RoomData],
    ) -> BenchmarkComparisonResponse:
        opt_metrics = cls.calculate_metrics("OR-Tools CP-SAT", optimizer_res, sessions, rooms)
        base_metrics = cls.calculate_metrics("First-Fit Baseline", baseline_res, sessions, rooms)

        is_better = (
            opt_metrics.allocation_rate >= base_metrics.allocation_rate
            and opt_metrics.seat_utilization >= base_metrics.seat_utilization
        )

        summary = (
            f"CP-SAT achieved {opt_metrics.allocation_rate}% allocation rate "
            f"({opt_metrics.allocated_sessions}/{opt_metrics.total_eligible_sessions}) with "
            f"{opt_metrics.seat_utilization}% seat utilization in {opt_metrics.runtime_ms}ms. "
            f"Baseline First-Fit achieved {base_metrics.allocation_rate}% allocation rate "
            f"({base_metrics.allocated_sessions}/{base_metrics.total_eligible_sessions}) with "
            f"{base_metrics.seat_utilization}% seat utilization in {base_metrics.runtime_ms}ms."
        )

        return BenchmarkComparisonResponse(
            allocation_run_id=run_id,
            optimizer_metrics=opt_metrics,
            baseline_first_fit_metrics=base_metrics,
            comparison_summary=summary,
            is_optimizer_better_or_equal=is_better,
        )

