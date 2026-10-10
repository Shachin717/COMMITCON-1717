from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Enum as SQLEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import RoomStatus, RoomType

if TYPE_CHECKING:
    from app.models.block import Block
    from app.models.department import Department
    from app.models.facility import Facility
    from app.models.timetable import TimetableEntry
    from app.models.room_block import RoomBlock
    from app.models.booking import Booking


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    block_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("blocks.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    floor: Mapped[int] = mapped_column(Integer, nullable=False)
    room_type: Mapped[RoomType] = mapped_column(
        SQLEnum(RoomType, name="room_type_enum", native_enum=True),
        nullable=False,
        index=True,
    )
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[RoomStatus] = mapped_column(
        SQLEnum(RoomStatus, name="room_status_enum", native_enum=True),
        default=RoomStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    maintenance_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    block: Mapped["Block"] = relationship("Block", back_populates="rooms")
    department: Mapped[Optional["Department"]] = relationship(
        "Department", back_populates="rooms"
    )
    facilities: Mapped[List["Facility"]] = relationship(
        "Facility", secondary="room_facilities", back_populates="rooms"
    )
    timetable_entries: Mapped[List["TimetableEntry"]] = relationship(
        "TimetableEntry", back_populates="room", cascade="all, delete-orphan"
    )
    room_blocks: Mapped[List["RoomBlock"]] = relationship(
        "RoomBlock", back_populates="room", cascade="all, delete-orphan"
    )
    bookings: Mapped[List["Booking"]] = relationship(
        "Booking", back_populates="room"
    )

