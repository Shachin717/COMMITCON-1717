from typing import TYPE_CHECKING
from sqlalchemy import Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.class_session import ClassSession
    from app.models.facility import Facility


class SessionFacility(Base):
    __tablename__ = "session_facilities"

    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("class_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    facility_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("facilities.id", ondelete="CASCADE"), primary_key=True
    )

    session: Mapped["ClassSession"] = relationship("ClassSession", back_populates="required_facilities")
    facility: Mapped["Facility"] = relationship("Facility", back_populates="session_facilities")

