from typing import TYPE_CHECKING
from sqlalchemy import Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.classroom import Classroom
    from app.models.department import Department


class RoomDepartmentAccess(Base):
    __tablename__ = "room_department_access"

    room_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("classrooms.id", ondelete="CASCADE"), primary_key=True
    )
    department_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True
    )

    classroom: Mapped["Classroom"] = relationship("Classroom", back_populates="department_accesses")
    department: Mapped["Department"] = relationship("Department", back_populates="lab_accesses")

