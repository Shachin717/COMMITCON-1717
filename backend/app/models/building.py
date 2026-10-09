from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.classroom import Classroom


class Building(Base):
    __tablename__ = "buildings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    classrooms: Mapped[List["Classroom"]] = relationship("Classroom", back_populates="building")

