from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.allocation_run import AllocationRun
    from app.models.class_session import ClassSession
    from app.models.classroom import Classroom


class Allocation(Base):
    __tablename__ = "allocations"
    __table_args__ = (
        UniqueConstraint("allocation_run_id", "class_session_id", name="uq_run_session_allocation"),
        CheckConstraint("status IN ('DRAFT', 'PUBLISHED')", name="check_allocation_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    allocation_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("allocation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("class_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    room_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    allocation_run: Mapped["AllocationRun"] = relationship("AllocationRun", back_populates="allocations")
    class_session: Mapped["ClassSession"] = relationship("ClassSession", back_populates="allocations")
    classroom: Mapped["Classroom"] = relationship("Classroom", back_populates="allocations")

