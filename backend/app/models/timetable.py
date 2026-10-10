from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.room import Room
    from app.models.time_slot import TimeSlot
    from app.models.department import Department


class TimetableEntry(Base):
    """Recurring fixed weekly class assigned to a room and time slot."""
    __tablename__ = "timetable_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day_of_week: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday"
    )
    slot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    department_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    faculty_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    room: Mapped["Room"] = relationship("Room", back_populates="timetable_entries")
    slot: Mapped["TimeSlot"] = relationship("TimeSlot", back_populates="timetable_entries")
    department: Mapped["Department"] = relationship("Department", back_populates="timetable_entries")

    __table_args__ = (
        UniqueConstraint("room_id", "day_of_week", "slot_id", name="uq_timetable_room_day_slot"),
        Index("ix_timetable_day_slot", "day_of_week", "slot_id"),
    )

