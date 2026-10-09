from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.building import Building
    from app.models.classroom_facility import ClassroomFacility
    from app.models.room_department_access import RoomDepartmentAccess
    from app.models.room_unavailability import RoomUnavailability
    from app.models.booking import Booking
    from app.models.allocation import Allocation


class Classroom(Base):
    __tablename__ = "classrooms"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="check_positive_capacity"),
        CheckConstraint("room_type IN ('CLASSROOM', 'LAB')", name="check_valid_room_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    building_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("buildings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    room_type: Mapped[str] = mapped_column(String(20), nullable=False, default="CLASSROOM")  # CLASSROOM or LAB
    location_description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    building: Mapped[Optional["Building"]] = relationship("Building", back_populates="classrooms")
    facilities: Mapped[List["ClassroomFacility"]] = relationship(
        "ClassroomFacility", back_populates="classroom", cascade="all, delete-orphan"
    )
    department_accesses: Mapped[List["RoomDepartmentAccess"]] = relationship(
        "RoomDepartmentAccess", back_populates="classroom", cascade="all, delete-orphan"
    )
    unavailabilities: Mapped[List["RoomUnavailability"]] = relationship(
        "RoomUnavailability", back_populates="classroom", cascade="all, delete-orphan"
    )
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="classroom")
    allocations: Mapped[List["Allocation"]] = relationship("Allocation", back_populates="classroom")

