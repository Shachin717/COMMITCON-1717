from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.room import Room
    from app.models.user import User


class BlockCoordinator(Base):
    """Many-to-many association between Users (Coordinators) and Blocks."""
    __tablename__ = "block_coordinators"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    block_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("blocks.id", ondelete="CASCADE"), primary_key=True
    )

    user: Mapped["User"] = relationship("User", back_populates="coordinator_assignments")
    block: Mapped["Block"] = relationship("Block", back_populates="coordinator_assignments")


class Block(Base):
    __tablename__ = "blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    rooms: Mapped[List["Room"]] = relationship(
        "Room", back_populates="block", cascade="all, delete-orphan"
    )
    coordinator_assignments: Mapped[List["BlockCoordinator"]] = relationship(
        "BlockCoordinator", back_populates="block", cascade="all, delete-orphan"
    )
    coordinators: Mapped[List["User"]] = relationship(
        "User", secondary="block_coordinators", viewonly=True
    )

