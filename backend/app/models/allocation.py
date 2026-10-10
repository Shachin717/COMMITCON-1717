from datetime import date, datetime
from typing import Any, Dict, Optional
from sqlalchemy import Date, DateTime, Float, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AllocationHistory(Base):
    """Historical records of allocation simulations and applied runs."""
    __tablename__ = "allocation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), default="SIMULATED", nullable=False, comment="SIMULATED or APPLIED"
    )
    date_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    date_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    total_requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    baseline_metrics: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    optimized_metrics: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

