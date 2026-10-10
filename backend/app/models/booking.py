from datetime import date, datetime
from typing import TYPE_CHECKING, Any, List, Optional
from sqlalchemy import Boolean, Date, DateTime, Enum as SQLEnum, ForeignKey, Index, Integer, JSON, String, Text, func, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Mapped, mapped_column, relationship


@compiles(ExcludeConstraint, "sqlite")
def _sqlite_exclude_constraint(element, compiler, **kw):
    # SQLite does not natively support Postgres EXCLUDE USING gist constraints
    return None

from app.models.base import Base
from app.models.enums import BookingStatus, RequesterType

if TYPE_CHECKING:
    from app.models.room import Room
    from app.models.time_slot import TimeSlot
    from app.models.department import Department
    from app.models.user import User


class Booking(Base):
    """Booking requests and allocations submitted by students and faculty."""
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reference: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False, comment="Unique short reference code"
    )
    room_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    slot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("time_slots.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    expected_strength: Mapped[int] = mapped_column(Integer, nullable=False)
    required_facilities: Mapped[List[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    status: Mapped[BookingStatus] = mapped_column(
        SQLEnum(BookingStatus, name="booking_status_enum", native_enum=True),
        default=BookingStatus.PENDING,
        nullable=False,
        index=True,
    )
    requires_hod_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requester_type: Mapped[RequesterType] = mapped_column(
        SQLEnum(RequesterType, name="requester_type_enum", native_enum=True),
        nullable=False,
        index=True,
    )
    roll_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    department_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    class_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    cancel_token_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    decided_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    decision_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reminder_sent: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )
    checked_in: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )

    # Relationships
    room: Mapped["Room"] = relationship("Room", back_populates="bookings")
    slot: Mapped["TimeSlot"] = relationship("TimeSlot", back_populates="bookings")
    department: Mapped["Department"] = relationship("Department", back_populates="bookings")
    decided_by_user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="decided_bookings"
    )

    __table_args__ = (
        # PostgreSQL EXCLUSION constraint using btree_gist to strictly prohibit overlapping active bookings
        ExcludeConstraint(
            ("room_id", "="),
            ("date", "="),
            ("slot_id", "="),
            name="exclude_overlapping_active_bookings",
            where=text("status IN ('PENDING', 'COORDINATOR_APPROVED', 'APPROVED')"),
            using="gist",
        ),
        Index(
            "uq_bookings_active_room_slot",
            "room_id",
            "date",
            "slot_id",
            unique=True,
            sqlite_where=text("status IN ('PENDING', 'COORDINATOR_APPROVED', 'APPROVED')"),
            postgresql_where=text("status IN ('PENDING', 'COORDINATOR_APPROVED', 'APPROVED')"),
        ),
        Index("ix_bookings_room_date_slot", "room_id", "date", "slot_id"),
        Index("ix_bookings_date_slot", "date", "slot_id"),
        Index("ix_bookings_status_date", "status", "date"),
    )

