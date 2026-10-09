from typing import TYPE_CHECKING
from sqlalchemy import Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.classroom import Classroom
    from app.models.facility import Facility


class ClassroomFacility(Base):
    __tablename__ = "classroom_facilities"

    classroom_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("classrooms.id", ondelete="CASCADE"), primary_key=True
    )
    facility_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("facilities.id", ondelete="CASCADE"), primary_key=True
    )

    classroom: Mapped["Classroom"] = relationship("Classroom", back_populates="facilities")
    facility: Mapped["Facility"] = relationship("Facility", back_populates="classroom_facilities")

