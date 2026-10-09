from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Integer, String, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.classroom import Classroom
    from app.models.department import Department
    from app.models.class_session import ClassSession
    from app.models.user import User


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("end_datetime > start_datetime", name="check_booking_end_after_start"),
        CheckConstraint("status IN ('PENDING', 'CONFIRMED', 'CANCELLED', 'PENDING_HOD_APPROVAL', 'APPROVED', 'REJECTED')", name="check_booking_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    room_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_session_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("classsessions.id" if False else "class_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    purpose: Mapped[Optional[str]] = mapped_column(
        String(50), default="REGULAR_CLASS", nullable=True
    )  # REGULAR_CLASS, EXAMINATION, MCQ_TEST, SEMINAR, WORKSHOP, EVENT, OTHER
    requested_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    classroom: Mapped["Classroom"] = relationship("Classroom", back_populates="bookings")
    department: Mapped[Optional["Department"]] = relationship("Department", back_populates="bookings")
    class_session: Mapped[Optional["ClassSession"]] = relationship("ClassSession", back_populates="bookings")
    requested_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[requested_by_user_id])
    
