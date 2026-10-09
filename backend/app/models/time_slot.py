from datetime import time
from typing import Optional
from sqlalchemy import Integer, String, Time, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class TimeSlot(Base):
    __tablename__ = "time_slots"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="check_slot_end_after_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

