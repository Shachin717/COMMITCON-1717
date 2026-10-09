from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, delete, update
from app.models.allocation_run import AllocationRun
from app.models.allocation import Allocation
from app.models.class_session import ClassSession
from app.models.classroom import Classroom


class AllocationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_run_by_id(self, run_id: int) -> Optional[AllocationRun]:
        stmt = (
            select(AllocationRun)
            .options(
                joinedload(AllocationRun.allocations)
                .joinedload(Allocation.class_session)
                .joinedload(ClassSession.class_group),
                joinedload(AllocationRun.allocations)
                .joinedload(Allocation.classroom),
            )
            .where(AllocationRun.id == run_id)
        )
        return self.db.scalars(stmt).unique().first()

    def get_all_runs(self, skip: int = 0, limit: int = 50) -> List[AllocationRun]:
        stmt = select(AllocationRun).order_by(AllocationRun.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def create_run(
        self,
        status: str,
        total_sessions: int,
        configuration: Optional[Dict[str, Any]] = None,
    ) -> AllocationRun:
        run = AllocationRun(
            status=status,
            total_sessions=total_sessions,
            configuration=configuration,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def update_run(
        self,
        run_id: int,
        status: str,
        objective_value: Optional[float] = None,
        solver_runtime_ms: float = 0.0,
        allocated_sessions: int = 0,
        unallocated_sessions: int = 0,
        error_message: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> AllocationRun:
        run = self.db.get(AllocationRun, run_id)
        if not run:
            raise ValueError(f"Allocation run {run_id} not found")
        run.status = status
        run.objective_value = objective_value
        run.solver_runtime_ms = solver_runtime_ms
        run.allocated_sessions = allocated_sessions
        run.unallocated_sessions = unallocated_sessions
        run.error_message = error_message
        if metrics is not None:
            run.metrics = metrics
        self.db.commit()
        return self.get_run_by_id(run_id)

    def save_allocations(
        self, run_id: int, session_room_pairs: List[tuple[int, int]], status: str = "DRAFT"
    ) -> List[Allocation]:
        # Delete any existing allocations for this run
        self.db.execute(delete(Allocation).where(Allocation.allocation_run_id == run_id))
        self.db.flush()

        created_allocations = []
        for session_id, room_id in session_room_pairs:
            alloc = Allocation(
                allocation_run_id=run_id,
                class_session_id=session_id,
                room_id=room_id,
                status=status,
            )
            self.db.add(alloc)
            created_allocations.append(alloc)

        self.db.commit()
        return created_allocations

    def get_published_allocations(self) -> List[Allocation]:
        stmt = (
            select(Allocation)
            .options(
                joinedload(Allocation.class_session),
                joinedload(Allocation.classroom),
            )
            .where(Allocation.status == "PUBLISHED")
        )
        return list(self.db.scalars(stmt).all())

    def publish_run(self, run_id: int) -> bool:
        """
        Publishes the specified allocation run.
        Marks all allocations of this run as PUBLISHED.
        """
        run = self.get_run_by_id(run_id)
        if not run:
            return False

        # Mark allocations for this run as PUBLISHED
        self.db.execute(
            update(Allocation)
            .where(Allocation.allocation_run_id == run_id)
            .values(status="PUBLISHED")
        )
        self.db.commit()
        return True

