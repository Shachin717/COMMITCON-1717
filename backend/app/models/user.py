from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.block import Block, BlockCoordinator
    from app.models.room_block import RoomBlock
    from app.models.booking import Booking


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role_enum", native_enum=True),
        nullable=False,
        index=True,
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    department: Mapped[Optional["Department"]] = relationship(
        "Department", back_populates="users"
    )
    coordinator_assignments: Mapped[List["BlockCoordinator"]] = relationship(
        "BlockCoordinator", back_populates="user", cascade="all, delete-orphan"
    )
    coordinated_blocks: Mapped[List["Block"]] = relationship(
        "Block", secondary="block_coordinators", viewonly=True
    )
    created_blocks: Mapped[List["RoomBlock"]] = relationship(
        "RoomBlock", foreign_keys="[RoomBlock.created_by]", back_populates="creator"
    )
    decided_bookings: Mapped[List["Booking"]] = relationship(
        "Booking", back_populates="decided_by_user"
    )

