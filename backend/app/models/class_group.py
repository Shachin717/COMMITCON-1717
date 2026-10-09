from datetime import datetime
from typing import List, TYPE_CHECKING
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.class_session import ClassSession


class ClassGroup(Base):
    __tablename__ = "class_groups"
    __table_args__ = (
        CheckConstraint("student_count >= 0", name="check_non_negative_student_count"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    department_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    student_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    department: Mapped["Department"] = relationship("Department", back_populates="class_groups")
    sessions: Mapped[List["ClassSession"]] = relationship(
        "ClassSession", back_populates="class_group", cascade="all, delete-orphan"
    )

