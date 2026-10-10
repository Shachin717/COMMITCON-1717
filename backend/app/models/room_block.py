from datetime import date, datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, Date, DateTime, Enum as SQLEnum, ForeignKey, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import RoomBlockReason

if TYPE_CHECKING:
    from app.models.room import Room
    from app.models.time_slot import TimeSlot
    from app.models.user import User


class RoomBlock(Base):
    """Room blackout periods for maintenance, exams, or institutional closures."""
    __tablename__ = "room_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    slot_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=True, index=True,
        comment="Null implies whole-day block"
    )
    reason: Mapped[RoomBlockReason] = mapped_column(
        SQLEnum(RoomBlockReason, name="room_block_reason_enum", native_enum=True),
        nullable=False,
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_released: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false", index=True
    )
    released_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    released_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=datetime.utcnow, nullable=False
    )

    # Relationships
    room: Mapped["Room"] = relationship("Room", back_populates="room_blocks")
    slot: Mapped[Optional["TimeSlot"]] = relationship("TimeSlot", back_populates="room_blocks")
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by], back_populates="created_blocks")
    releaser: Mapped[Optional["User"]] = relationship("User", foreign_keys=[released_by])

    __table_args__ = (
        Index("ix_room_blocks_room_date", "room_id", "date"),
    )

