from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.classroom_facility import ClassroomFacility
    from app.models.session_facility import SessionFacility


class Facility(Base):
    __tablename__ = "facilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    classroom_facilities: Mapped[List["ClassroomFacility"]] = relationship(
        "ClassroomFacility", back_populates="facility", cascade="all, delete-orphan"
    )
    session_facilities: Mapped[List["SessionFacility"]] = relationship(
        "SessionFacility", back_populates="facility", cascade="all, delete-orphan"
    )

