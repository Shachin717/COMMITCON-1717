from typing import TYPE_CHECKING, List
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.room import Room


class RoomFacility(Base):
    """Many-to-many association between Rooms and Facilities."""
    __tablename__ = "room_facilities"

    room_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True
    )
    facility_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("facilities.id", ondelete="CASCADE"), primary_key=True
    )


class Facility(Base):
    __tablename__ = "facilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)

    # Relationships
    rooms: Mapped[List["Room"]] = relationship(
        "Room", secondary="room_facilities", back_populates="facilities"
    )

