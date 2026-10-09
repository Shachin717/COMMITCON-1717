from datetime import date, time
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import Integer, String, Date, Time, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.class_group import ClassGroup
    from app.models.session_facility import SessionFacility
    from app.models.booking import Booking
    from app.models.allocation import Allocation


class ClassSession(Base):
    __tablename__ = "class_sessions"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="check_session_end_after_start"),
        CheckConstraint("required_room_type IN ('CLASSROOM', 'LAB')", name="check_session_room_type"),
        CheckConstraint("status IN ('ACTIVE', 'CANCELLED')", name="check_session_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    class_group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("class_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    required_room_type: Mapped[str] = mapped_column(String(20), nullable=False, default="CLASSROOM")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    class_group: Mapped["ClassGroup"] = relationship("ClassGroup", back_populates="sessions")
    required_facilities: Mapped[List["SessionFacility"]] = relationship(
        "SessionFacility", back_populates="session", cascade="all, delete-orphan"
    )
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="class_session")
    allocations: Mapped[List["Allocation"]] = relationship("Allocation", back_populates="class_session")

