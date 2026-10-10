from datetime import date, datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.room import Room
    from app.models.time_slot import TimeSlot
    from app.models.department import Department


class WaitlistEntry(Base):
    """Waitlist requests for unavailable rooms and time slots."""
    __tablename__ = "waitlist_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    slot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    roll_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    class_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    room: Mapped["Room"] = relationship("Room")
    slot: Mapped["TimeSlot"] = relationship("TimeSlot")
    department: Mapped[Optional["Department"]] = relationship("Department")

    __table_args__ = (
        Index("ix_waitlist_room_date_slot_notified", "room_id", "date", "slot_id", "notified"),
    )

