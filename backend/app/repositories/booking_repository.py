from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, and_, or_
from app.models.booking import Booking
from app.models.classroom import Classroom
from app.models.room_unavailability import RoomUnavailability
from app.models.allocation import Allocation
from app.models.class_session import ClassSession
from app.schemas.booking import BookingCreate, BookingUpdate, RoomUnavailabilityCreate


class BookingRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, booking_id: int) -> Optional[Booking]:
        stmt = (
            select(Booking)
            .options(joinedload(Booking.classroom), joinedload(Booking.department))
            .where(Booking.id == booking_id)
        )
        return self.db.scalars(stmt).first()

    def get_all(
        self,
        room_id: Optional[int] = None,
        status: Optional[str] = None,
        start_datetime: Optional[datetime] = None,
        end_datetime: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Booking]:
        stmt = select(Booking).options(joinedload(Booking.classroom), joinedload(Booking.department))
        if room_id is not None:
            stmt = stmt.where(Booking.room_id == room_id)
        if status is not None:
            stmt = stmt.where(Booking.status == status)
        if start_datetime is not None and end_datetime is not None:
            # Overlap: existing_start < requested_end AND requested_start < existing_end
            stmt = stmt.where(
                and_(
                    Booking.start_datetime < end_datetime,
                    start_datetime < Booking.end_datetime,
                )
            )
        return list(self.db.scalars(stmt.offset(skip).limit(limit)).all())

    def lock_room(self, room_id: int) -> Optional[Classroom]:
        """
        Locks the room row to ensure race-free concurrency across transactions.
        On SQLite, transactions are database-wide locked; on PostgreSQL, this executes FOR UPDATE.
        """
        stmt = select(Classroom).where(Classroom.id == room_id)
        bind = self.db.get_bind()
        if bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.db.scalars(stmt).first()

    def check_conflicts(
        self,
        room_id: int,
        start_dt: datetime,
        end_dt: datetime,
        exclude_booking_id: Optional[int] = None,
    ) -> Dict[str, List[Any]]:
        """
        Detects any overlapping confirmed bookings, maintenance periods, or published class allocations.
        Overlap condition: existing_start < requested_end AND requested_start < existing_end.
        """
        # 1. Confirmed bookings and Pending HOD Approval bookings
        b_stmt = select(Booking).where(
            Booking.room_id == room_id,
            Booking.status.in_(["CONFIRMED", "PENDING_HOD_APPROVAL"]),
            Booking.start_datetime < end_dt,
            start_dt < Booking.end_datetime,
        )
        if exclude_booking_id:
            b_stmt = b_stmt.where(Booking.id != exclude_booking_id)
        conflicting_bookings = list(self.db.scalars(b_stmt).all())

        # 2. Maintenance periods (RoomUnavailability)
        m_stmt = select(RoomUnavailability).where(
            RoomUnavailability.room_id == room_id,
            RoomUnavailability.start_datetime < end_dt,
            start_dt < RoomUnavailability.end_datetime,
        )
        conflicting_maintenance = list(self.db.scalars(m_stmt).all())

        # 3. Published allocations
        # Compare session datetime with requested start_dt and end_dt
        a_stmt = (
            select(Allocation)
            .join(ClassSession, Allocation.class_session_id == ClassSession.id)
            .where(
                Allocation.room_id == room_id,
                Allocation.status == "PUBLISHED",
                ClassSession.status == "ACTIVE",
            )
        )
        published_allocations = list(self.db.scalars(a_stmt).all())
        conflicting_allocations = []
        for alloc in published_allocations:
            sess = alloc.class_session
            sess_start = datetime.combine(sess.session_date, sess.start_time)
            sess_end = datetime.combine(sess.session_date, sess.end_time)
            if sess_start.tzinfo is None and start_dt.tzinfo is not None:
                sess_start = sess_start.replace(tzinfo=start_dt.tzinfo)
                sess_end = sess_end.replace(tzinfo=start_dt.tzinfo)
            elif sess_start.tzinfo is not None and start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=sess_start.tzinfo)
                end_dt = end_dt.replace(tzinfo=sess_start.tzinfo)

            if sess_start < end_dt and start_dt < sess_end:
                conflicting_allocations.append(alloc)

        return {
            "bookings": conflicting_bookings,
            "maintenance": conflicting_maintenance,
            "allocations": conflicting_allocations,
        }

    def create(self, obj_in: BookingCreate, requested_by_user_id: Optional[int] = None) -> Booking:
        db_obj = Booking(
            room_id=obj_in.room_id,
            title=obj_in.title,
            start_datetime=obj_in.start_datetime,
            end_datetime=obj_in.end_datetime,
            class_session_id=obj_in.class_session_id,
            department_id=obj_in.department_id,
            status=obj_in.status,
            purpose=obj_in.purpose,
            requested_by_user_id=requested_by_user_id,
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, db_obj: Booking, obj_in: BookingUpdate) -> Booking:
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def cancel(self, booking_id: int) -> Optional[Booking]:
        db_obj = self.get_by_id(booking_id)
        if not db_obj:
            return None
        db_obj.status = "CANCELLED"
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    # Room Unavailability
    def create_unavailability(self, obj_in: RoomUnavailabilityCreate) -> RoomUnavailability:
        db_obj = RoomUnavailability(
            room_id=obj_in.room_id,
            start_datetime=obj_in.start_datetime,
            end_datetime=obj_in.end_datetime,
            reason=obj_in.reason,
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def get_unavailabilities(
        self, room_id: Optional[int] = None, skip: int = 0, limit: int = 100
    ) -> List[RoomUnavailability]:
        stmt = select(RoomUnavailability)
        if room_id is not None:
            stmt = stmt.where(RoomUnavailability.room_id == room_id)
        return list(self.db.scalars(stmt.offset(skip).limit(limit)).all())

    def delete_unavailability(self, unavailability_id: int) -> bool:
        db_obj = self.db.get(RoomUnavailability, unavailability_id)
        if not db_obj:
            return False
        self.db.delete(db_obj)
        self.db.commit()
        return True

