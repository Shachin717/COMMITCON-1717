from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.classroom import Classroom
from app.models.class_session import ClassSession
from app.models.booking import Booking
from app.models.room_unavailability import RoomUnavailability
from app.models.allocation import Allocation
from app.models.allocation_run import AllocationRun

from app.repositories.allocation_repository import AllocationRepository
from app.repositories.classroom_repository import ClassroomRepository
from app.repositories.booking_repository import BookingRepository
from app.repositories.schedule_repository import ScheduleRepository

from app.optimizer.constraints import SessionData, RoomData, TimeBlock
from app.optimizer.objective import ObjectiveConfig
from app.optimizer.solver import (
    OrToolsAllocationSolver,
    FirstFitBaselineSolver,
    OptimizationSolverResult,
)
from app.optimizer.result_validator import AllocationResultValidator

from app.schemas.allocation import (
    AllocationGenerateRequest,
    AllocationRunResponse,
    AllocationItemResponse,
    ReallocationSummary,
)
from app.schemas.class_session import ClassSessionResponse
from app.schemas.classroom import ClassroomResponse
from app.services.schedule_service import ScheduleService
from app.services.classroom_service import ClassroomService
from app.services.metrics_service import MetricsService

from app.core.exceptions import (
    ResourceNotFoundException,
    ConflictException,
    ValidationBusinessException,
)


class AllocationService:
    def __init__(self, db: Session):
        self.db = db
        self.alloc_repo = AllocationRepository(db)
        self.room_repo = ClassroomRepository(db)
        self.booking_repo = BookingRepository(db)
        self.schedule_repo = ScheduleRepository(db)
        self.schedule_service = ScheduleService(db)
        self.room_service = ClassroomService(db)

    def _extract_session_data(self, sessions: List[ClassSession]) -> List[SessionData]:
        result = []
        for s in sessions:
            fac_ids = {sf.facility_id for sf in s.required_facilities}
            dept_id = s.class_group.department_id if s.class_group else 0
            student_count = s.class_group.student_count if s.class_group else 0
            result.append(
                SessionData(
                    id=s.id,
                    class_group_id=s.class_group_id,
                    department_id=dept_id,
                    student_count=student_count,
                    session_date=s.session_date,
                    start_time=s.start_time,
                    end_time=s.end_time,
                    required_room_type=s.required_room_type,
                    required_facility_ids=fac_ids,
                )
            )
        return result

    def _extract_room_data(self, rooms: List[Classroom]) -> List[RoomData]:
        result = []
        for r in rooms:
            fac_ids = {cf.facility_id for cf in r.facilities}
            auth_depts = {da.department_id for da in r.department_accesses}
            result.append(
                RoomData(
                    id=r.id,
                    name=r.name,
                    capacity=r.capacity,
                    room_type=r.room_type,
                    building_id=r.building_id,
                    is_active=r.is_active,
                    facility_ids=fac_ids,
                    authorized_department_ids=auth_depts,
                )
            )
        return result

    def _build_external_constraints(
        self,
    ) -> Tuple[
        Dict[int, List[TimeBlock]],
        Dict[int, List[TimeBlock]],
        Dict[int, List[Tuple[int, TimeBlock]]],
    ]:
        # 1. Maintenance
        unavs = self.db.scalars(select(RoomUnavailability)).all()
        m_map: Dict[int, List[TimeBlock]] = {}
        for u in unavs:
            m_map.setdefault(u.room_id, []).append(
                TimeBlock(start_datetime=u.start_datetime, end_datetime=u.end_datetime)
            )

        # 2. Confirmed bookings
        bookings = self.db.scalars(
            select(Booking).where(Booking.status == "CONFIRMED")
        ).all()
        b_map: Dict[int, List[TimeBlock]] = {}
        for b in bookings:
            b_map.setdefault(b.room_id, []).append(
                TimeBlock(start_datetime=b.start_datetime, end_datetime=b.end_datetime)
            )

        # 3. Published allocations
        published = self.db.scalars(
            select(Allocation)
            .join(ClassSession)
            .where(Allocation.status == "PUBLISHED", ClassSession.status == "ACTIVE")
        ).all()
        p_map: Dict[int, List[Tuple[int, TimeBlock]]] = {}
        for a in published:
            s = a.class_session
            s_start = datetime.combine(s.session_date, s.start_time)
            s_end = datetime.combine(s.session_date, s.end_time)
            p_map.setdefault(a.room_id, []).append(
                (a.class_session_id, TimeBlock(start_datetime=s_start, end_datetime=s_end))
            )

        return m_map, b_map, p_map

    def _run_to_response(self, run: AllocationRun) -> AllocationRunResponse:
        alloc_items = []
        for a in run.allocations:
            alloc_items.append(
                AllocationItemResponse(
                    id=a.id,
                    allocation_run_id=a.allocation_run_id,
                    class_session_id=a.class_session_id,
                    room_id=a.room_id,
                    status=a.status,
                    created_at=a.created_at,
                    updated_at=a.updated_at,
                    class_session=self.schedule_service._session_to_response(a.class_session)
                    if a.class_session
                    else None,
                    classroom=self.room_service._to_response(a.classroom)
                    if a.classroom
                    else None,
                )
            )

        all_sess_ids = []
        if run.configuration and "session_ids" in run.configuration:
            all_sess_ids = run.configuration["session_ids"]
        allocated_sids = {a.class_session_id for a in run.allocations}
        unallocated_sids = [sid for sid in all_sess_ids if sid not in allocated_sids]

        return AllocationRunResponse(
            id=run.id,
            status=run.status,
            objective_value=run.objective_value,
            solver_runtime_ms=run.solver_runtime_ms,
            allocated_sessions=run.allocated_sessions,
            unallocated_sessions=run.unallocated_sessions,
            total_sessions=run.total_sessions,
            created_at=run.created_at,
            completed_at=run.completed_at,
            error_message=run.error_message,
            configuration=run.configuration,
            allocations=alloc_items,
            unallocated_session_ids=unallocated_sids,
        )

    def generate_allocation(self, req: AllocationGenerateRequest) -> AllocationRunResponse:
        # 1. Fetch sessions to allocate
        stmt = select(ClassSession).where(ClassSession.status == "ACTIVE")
        if req.session_ids is not None:
            stmt = stmt.where(ClassSession.id.in_(req.session_ids))
        if req.start_date is not None:
            stmt = stmt.where(ClassSession.session_date >= req.start_date)
        if req.end_date is not None:
            stmt = stmt.where(ClassSession.session_date <= req.end_date)

        db_sessions = list(self.db.scalars(stmt).unique().all())
        db_rooms = self.room_repo.get_all(is_active=True, limit=1000)

        session_data = self._extract_session_data(db_sessions)
        room_data = self._extract_room_data(db_rooms)

        # External constraints
        m_map, b_map, p_map = self._build_external_constraints()

        # If we are allocating sessions that are currently published, remove them from p_map
        allocated_sids_set = {s.id for s in session_data}
        for rid, items in p_map.items():
            p_map[rid] = [(sid, block) for sid, block in items if sid not in allocated_sids_set]

        # Configure Solver
        settings_obj = req.settings
        obj_cfg = ObjectiveConfig(
            weight_unallocated=settings_obj.weight_unallocated if settings_obj else None,
            weight_seat_waste=settings_obj.weight_seat_waste if settings_obj else None,
            weight_preference=settings_obj.weight_preference if settings_obj else None,
            weight_reallocation_change=settings_obj.weight_reallocation_change if settings_obj else None,
        )
        solver = OrToolsAllocationSolver(
            time_limit_seconds=settings_obj.time_limit_seconds if settings_obj else 30.0,
            random_seed=settings_obj.random_seed if settings_obj else 42,
            num_workers=settings_obj.num_workers if settings_obj else 4,
            objective_config=obj_cfg,
        )

        # Baseline comparison
        baseline_solver = FirstFitBaselineSolver()
        baseline_result = baseline_solver.solve(
            sessions=session_data,
            rooms=room_data,
            room_unavailabilities=m_map,
            confirmed_bookings=b_map,
            published_allocations=p_map,
        )

        # Run CP-SAT solver
        solver_result: OptimizationSolverResult = solver.solve(
            sessions=session_data,
            rooms=room_data,
            room_unavailabilities=m_map,
            confirmed_bookings=b_map,
            published_allocations=p_map,
        )

        # Initialize AllocationRun in DB
        config_payload = {
            "session_ids": [s.id for s in session_data],
            "start_date": str(req.start_date) if req.start_date else None,
            "end_date": str(req.end_date) if req.end_date else None,
            "settings": settings_obj.model_dump() if settings_obj else {},
        }
        run = self.alloc_repo.create_run(
            status="RUNNING",
            total_sessions=len(session_data),
            configuration=config_payload,
        )

        # Calculate metrics and benchmark
        benchmark_resp = MetricsService.compare_benchmark(
            run_id=run.id,
            optimizer_res=solver_result,
            baseline_res=baseline_result,
            sessions=session_data,
            rooms=room_data,
        )

        # Save allocations if feasible/optimal
        if solver_result.is_feasible:
            pairs = list(solver_result.allocations.items())
            self.alloc_repo.save_allocations(run.id, pairs, status="DRAFT")

        updated_run = self.alloc_repo.update_run(
            run_id=run.id,
            status=solver_result.status,
            objective_value=solver_result.objective_value,
            solver_runtime_ms=solver_result.solver_runtime_ms,
            allocated_sessions=len(solver_result.allocations),
            unallocated_sessions=len(solver_result.unallocated_session_ids),
            error_message=solver_result.error_message,
            metrics=benchmark_resp.model_dump(),
        )

        return self._run_to_response(updated_run)

    def get_allocation_run(self, run_id: int) -> AllocationRunResponse:
        run = self.alloc_repo.get_run_by_id(run_id)
        if not run:
            raise ResourceNotFoundException("AllocationRun", run_id)
        return self._run_to_response(run)

    def list_allocation_runs(self, skip: int = 0, limit: int = 50) -> List[AllocationRunResponse]:
        runs = self.alloc_repo.get_all_runs(skip=skip, limit=limit)
        return [self._run_to_response(r) for r in runs]

    def publish_allocation(self, run_id: int) -> AllocationRunResponse:
        run = self.alloc_repo.get_run_by_id(run_id)
        if not run:
            raise ResourceNotFoundException("AllocationRun", run_id)

        if run.status not in ("OPTIMAL", "FEASIBLE"):
            raise ValidationBusinessException(
                f"Cannot publish run with status '{run.status}'. Only OPTIMAL or FEASIBLE drafts can be published."
            )

        # Independent re-validation before publishing
        session_map = {a.class_session.id: a.class_session for a in run.allocations if a.class_session}
        room_map = {a.classroom.id: a.classroom for a in run.allocations if a.classroom}

        sess_data = self._extract_session_data(list(session_map.values()))
        rm_data = self._extract_room_data(list(room_map.values()))
        m_map, b_map, p_map = self._build_external_constraints()

        # Remove our own draft allocations from p_map if any exist
        current_draft_sids = set(session_map.keys())
        for rid in p_map:
            p_map[rid] = [(sid, blk) for sid, blk in p_map[rid] if sid not in current_draft_sids]

        candidate_allocations = {a.class_session_id: a.room_id for a in run.allocations}

        violations = AllocationResultValidator.validate(
            allocations=candidate_allocations,
            sessions={s.id: s for s in sess_data},
            rooms={r.id: r for r in rm_data},
            room_unavailabilities=m_map,
            confirmed_bookings=b_map,
            published_allocations=p_map,
        )

        if violations:
            raise ConflictException(
                f"Cannot publish allocation run #{run_id}: Current system conditions conflict with this draft: "
                f"{'; '.join(violations[:3])}"
            )

        self.alloc_repo.publish_run(run_id)
        refreshed = self.alloc_repo.get_run_by_id(run_id)
        return self._run_to_response(refreshed)

    def reoptimize(self, run_id: int) -> ReallocationSummary:
        """
        Dynamic reallocation: re-runs optimization while penalizing disturbance of unaffected assignments.
        """
        previous_run = self.alloc_repo.get_run_by_id(run_id)
        if not previous_run:
            raise ResourceNotFoundException("AllocationRun", run_id)

        previous_allocations = {a.class_session_id: a.room_id for a in previous_run.allocations}

        # Collect session IDs
        session_ids = list(previous_allocations.keys())
        if previous_run.configuration and "session_ids" in previous_run.configuration:
            session_ids = list(set(session_ids + previous_run.configuration["session_ids"]))

        db_sessions = list(
            self.db.scalars(
                select(ClassSession).where(
                    ClassSession.id.in_(session_ids), ClassSession.status == "ACTIVE"
                )
            ).unique().all()
        )
        db_rooms = self.room_repo.get_all(is_active=True, limit=1000)

        session_data = self._extract_session_data(db_sessions)
        room_data = self._extract_room_data(db_rooms)

        m_map, b_map, p_map = self._build_external_constraints()
        # Filter out session IDs being reallocated from p_map
        for rid in p_map:
            p_map[rid] = [(sid, blk) for sid, blk in p_map[rid] if sid not in previous_allocations]

        # Use solver with reallocation stability weight
        obj_cfg = ObjectiveConfig(weight_reallocation_change=500)
        solver = OrToolsAllocationSolver(objective_config=obj_cfg)

        solver_result = solver.solve(
            sessions=session_data,
            rooms=room_data,
            room_unavailabilities=m_map,
            confirmed_bookings=b_map,
            published_allocations=p_map,
            previous_allocations=previous_allocations,
        )

        # Create new DRAFT run
        new_run = self.alloc_repo.create_run(
            status="RUNNING",
            total_sessions=len(session_data),
            configuration={
                "reallocated_from_run_id": run_id,
                "session_ids": [s.id for s in session_data],
            },
        )

        if solver_result.is_feasible:
            pairs = list(solver_result.allocations.items())
            self.alloc_repo.save_allocations(new_run.id, pairs, status="DRAFT")

        updated_run = self.alloc_repo.update_run(
            run_id=new_run.id,
            status=solver_result.status,
            objective_value=solver_result.objective_value,
            solver_runtime_ms=solver_result.solver_runtime_ms,
            allocated_sessions=len(solver_result.allocations),
            unallocated_sessions=len(solver_result.unallocated_session_ids),
            error_message=solver_result.error_message,
        )

        # Analyze changes
        changed_sids = []
        retained_count = 0
        newly_allocated_count = 0

        for sid, new_rid in solver_result.allocations.items():
            if sid in previous_allocations:
                old_rid = previous_allocations[sid]
                if old_rid != new_rid:
                    changed_sids.append(sid)
                else:
                    retained_count += 1
            else:
                newly_allocated_count += 1

        run_resp = self._run_to_response(updated_run)
        return ReallocationSummary(
            run_id=new_run.id,
            changed_count=len(changed_sids),
            retained_count=retained_count,
            newly_allocated_count=newly_allocated_count,
            unallocated_count=len(solver_result.unallocated_session_ids),
            changed_session_ids=changed_sids,
            allocation_run=run_resp,
        )

