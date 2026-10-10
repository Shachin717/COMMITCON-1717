from datetime import time
from typing import TYPE_CHECKING, List
from sqlalchemy import Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.timetable import TimetableEntry
    from app.models.booking import Booking
    from app.models.room_block import RoomBlock


class TimeSlot(Base):
    __tablename__ = "time_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)

    # Relationships
    timetable_entries: Mapped[List["TimetableEntry"]] = relationship(
        "TimetableEntry", back_populates="slot"
    )
    bookings: Mapped[List["Booking"]] = relationship(
        "Booking", back_populates="slot"
    )
    room_blocks: Mapped[List["RoomBlock"]] = relationship(
        "RoomBlock", back_populates="slot"
    )

