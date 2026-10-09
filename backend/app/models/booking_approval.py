from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
from app.models.booking import Booking
from app.models.user import User

class BookingApproval(Base):
    __tablename__ = "booking_approvals"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    booking_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    approver_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # APPROVED, REJECTED
    remarks: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    booking: Mapped["Booking"] = relationship("Booking", backref="approvals")
    approver: Mapped["User"] = relationship("User")
