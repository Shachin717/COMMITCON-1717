from datetime import datetime
from typing import List, Optional, Any, Dict, TYPE_CHECKING
from sqlalchemy import Integer, String, Float, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.allocation import Allocation


class AllocationRun(Base):
    __tablename__ = "allocation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="PENDING", nullable=False, index=True
    )  # PENDING, RUNNING, OPTIMAL, FEASIBLE, INFEASIBLE, ERROR
    objective_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    solver_runtime_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    allocated_sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unallocated_sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    configuration: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    allocations: Mapped[List["Allocation"]] = relationship(
        "Allocation", back_populates="allocation_run", cascade="all, delete-orphan"
    )

