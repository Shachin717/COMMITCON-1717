from datetime import date, time
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, and_, delete
from app.models.class_group import ClassGroup
from app.models.class_session import ClassSession
from app.models.session_facility import SessionFacility
from app.models.time_slot import TimeSlot
from app.schemas.class_group import ClassGroupCreate, ClassGroupUpdate
from app.schemas.class_session import ClassSessionCreate, ClassSessionUpdate, TimeSlotCreate


class ScheduleRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- Class Groups ---
    def get_group_by_id(self, group_id: int) -> Optional[ClassGroup]:
        stmt = (
            select(ClassGroup)
            .options(joinedload(ClassGroup.department))
            .where(ClassGroup.id == group_id)
        )
        return self.db.scalars(stmt).first()

    def get_all_groups(
        self, department_id: Optional[int] = None, is_active: Optional[bool] = None, skip: int = 0, limit: int = 100
    ) -> List[ClassGroup]:
        stmt = select(ClassGroup).options(joinedload(ClassGroup.department))
        if department_id is not None:
            stmt = stmt.where(ClassGroup.department_id == department_id)
        if is_active is not None:
            stmt = stmt.where(ClassGroup.is_active == is_active)
        return list(self.db.scalars(stmt.offset(skip).limit(limit)).all())

    def create_group(self, obj_in: ClassGroupCreate) -> ClassGroup:
        db_obj = ClassGroup(
            name=obj_in.name,
            department_id=obj_in.department_id,
            student_count=obj_in.student_count,
            is_active=obj_in.is_active,
        )
        self.db.add(db_obj)
        self.db.commit()
        return self.get_group_by_id(db_obj.id)

    def update_group(self, db_obj: ClassGroup, obj_in: ClassGroupUpdate) -> ClassGroup:
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        self.db.commit()
        return self.get_group_by_id(db_obj.id)

    # --- Class Sessions ---
    def get_session_by_id(self, session_id: int) -> Optional[ClassSession]:
        stmt = (
            select(ClassSession)
            .options(
                joinedload(ClassSession.class_group).joinedload(ClassGroup.department),
                joinedload(ClassSession.required_facilities).joinedload(SessionFacility.facility),
            )
            .where(ClassSession.id == session_id)
        )
        return self.db.scalars(stmt).unique().first()

    def get_all_sessions(
        self,
        class_group_id: Optional[int] = None,
        session_date: Optional[date] = None,
        status: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ClassSession]:
        stmt = select(ClassSession).options(
            joinedload(ClassSession.class_group).joinedload(ClassGroup.department),
            joinedload(ClassSession.required_facilities).joinedload(SessionFacility.facility),
        )
        if class_group_id is not None:
            stmt = stmt.where(ClassSession.class_group_id == class_group_id)
        if session_date is not None:
            stmt = stmt.where(ClassSession.session_date == session_date)
        if status is not None:
            stmt = stmt.where(ClassSession.status == status)
        if start_date is not None:
            stmt = stmt.where(ClassSession.session_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(ClassSession.session_date <= end_date)

        return list(self.db.scalars(stmt.offset(skip).limit(limit)).unique().all())

    def check_class_group_overlap(
        self,
        class_group_id: int,
        session_date: date,
        start_time: time,
        end_time: time,
        exclude_session_id: Optional[int] = None,
    ) -> List[ClassSession]:
        """
        Detects active overlapping sessions for the same class group on the same date.
        Overlap: existing_start < requested_end AND requested_start < existing_end.
        """
        stmt = select(ClassSession).where(
            ClassSession.class_group_id == class_group_id,
            ClassSession.session_date == session_date,
            ClassSession.status == "ACTIVE",
            ClassSession.start_time < end_time,
            start_time < ClassSession.end_time,
        )
        if exclude_session_id:
            stmt = stmt.where(ClassSession.id != exclude_session_id)
        return list(self.db.scalars(stmt).all())

    def create_session(self, obj_in: ClassSessionCreate) -> ClassSession:
        db_obj = ClassSession(
            class_group_id=obj_in.class_group_id,
            session_date=obj_in.session_date,
            start_time=obj_in.start_time,
            end_time=obj_in.end_time,
            required_room_type=obj_in.required_room_type,
            status=obj_in.status,
            notes=obj_in.notes,
        )
        self.db.add(db_obj)
        self.db.flush()

        if obj_in.required_facility_ids:
            for fac_id in set(obj_in.required_facility_ids):
                self.db.add(SessionFacility(session_id=db_obj.id, facility_id=fac_id))
            self.db.flush()

        self.db.commit()
        return self.get_session_by_id(db_obj.id)

    def update_session(self, db_obj: ClassSession, obj_in: ClassSessionUpdate) -> ClassSession:
        update_data = obj_in.model_dump(exclude_unset=True, exclude={"required_facility_ids"})
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        if obj_in.required_facility_ids is not None:
            self.db.execute(delete(SessionFacility).where(SessionFacility.session_id == db_obj.id))
            self.db.flush()
            for fac_id in set(obj_in.required_facility_ids):
                self.db.add(SessionFacility(session_id=db_obj.id, facility_id=fac_id))

        self.db.commit()
        return self.get_session_by_id(db_obj.id)

    def delete_session(self, session_id: int) -> bool:
        db_obj = self.get_session_by_id(session_id)
        if not db_obj:
            return False
        self.db.delete(db_obj)
        self.db.commit()
        return True

    # --- Time Slots ---
    def get_time_slots(self) -> List[TimeSlot]:
        return list(self.db.scalars(select(TimeSlot).order_by(TimeSlot.start_time)).all())

    def create_time_slot(self, obj_in: TimeSlotCreate) -> TimeSlot:
        db_obj = TimeSlot(name=obj_in.name, start_time=obj_in.start_time, end_time=obj_in.end_time)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

