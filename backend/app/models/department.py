from datetime import datetime
from typing import List, TYPE_CHECKING
from sqlalchemy import Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.class_group import ClassGroup
    from app.models.room_department_access import RoomDepartmentAccess
    from app.models.booking import Booking


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    class_groups: Mapped[List["ClassGroup"]] = relationship("ClassGroup", back_populates="department")
    lab_accesses: Mapped[List["RoomDepartmentAccess"]] = relationship(
        "RoomDepartmentAccess", back_populates="department", cascade="all, delete-orphan"
    )
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="department")

