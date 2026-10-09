from datetime import date, time
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.class_group import ClassGroup
from app.models.class_session import ClassSession
from app.models.department import Department
from app.models.facility import Facility
from app.models.time_slot import TimeSlot
from app.schemas.class_group import ClassGroupCreate, ClassGroupUpdate, ClassGroupResponse
from app.schemas.class_session import (
    ClassSessionCreate,
    ClassSessionUpdate,
    ClassSessionResponse,
    TimeSlotCreate,
    TimeSlotResponse,
    FacilityResponse,
)
from app.repositories.schedule_repository import ScheduleRepository
from app.core.exceptions import (
    ResourceNotFoundException,
    ConflictException,
    ValidationBusinessException,
)


class ScheduleService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ScheduleRepository(db)

    def _session_to_response(self, sess: ClassSession) -> ClassSessionResponse:
        fac_resps = [
            FacilityResponse(
                id=sf.facility.id,
                name=sf.facility.name,
                description=sf.facility.description,
            )
            for sf in sess.required_facilities
            if sf.facility
        ]
        return ClassSessionResponse(
            id=sess.id,
            class_group_id=sess.class_group_id,
            session_date=sess.session_date,
            start_time=sess.start_time,
            end_time=sess.end_time,
            required_room_type=sess.required_room_type,
            status=sess.status,
            notes=sess.notes,
            class_group=ClassGroupResponse.model_validate(sess.class_group) if sess.class_group else None,
            required_facilities=fac_resps,
        )

    # --- Class Groups ---
    def get_group(self, group_id: int) -> ClassGroupResponse:
        g = self.repo.get_group_by_id(group_id)
        if not g:
            raise ResourceNotFoundException("ClassGroup", group_id)
        return ClassGroupResponse.model_validate(g)

    def list_groups(
        self, department_id: Optional[int] = None, is_active: Optional[bool] = None, skip: int = 0, limit: int = 100
    ) -> List[ClassGroupResponse]:
        groups = self.repo.get_all_groups(department_id=department_id, is_active=is_active, skip=skip, limit=limit)
        return [ClassGroupResponse.model_validate(g) for g in groups]

    def create_group(self, obj_in: ClassGroupCreate) -> ClassGroupResponse:
        dept = self.db.get(Department, obj_in.department_id)
        if not dept:
            raise ResourceNotFoundException("Department", obj_in.department_id)
        if obj_in.student_count < 0:
            raise ValidationBusinessException("student_count cannot be negative.")

        g = self.repo.create_group(obj_in)
        return ClassGroupResponse.model_validate(g)

    def update_group(self, group_id: int, obj_in: ClassGroupUpdate) -> ClassGroupResponse:
        g = self.repo.get_group_by_id(group_id)
        if not g:
            raise ResourceNotFoundException("ClassGroup", group_id)
        if obj_in.department_id:
            dept = self.db.get(Department, obj_in.department_id)
            if not dept:
                raise ResourceNotFoundException("Department", obj_in.department_id)
        if obj_in.student_count is not None and obj_in.student_count < 0:
            raise ValidationBusinessException("student_count cannot be negative.")

        updated = self.repo.update_group(g, obj_in)
        return ClassGroupResponse.model_validate(updated)

    # --- Class Sessions ---
    def get_session(self, session_id: int) -> ClassSessionResponse:
        s = self.repo.get_session_by_id(session_id)
        if not s:
            raise ResourceNotFoundException("ClassSession", session_id)
        return self._session_to_response(s)

    def list_sessions(
        self,
        class_group_id: Optional[int] = None,
        session_date: Optional[date] = None,
        status: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ClassSessionResponse]:
        sessions = self.repo.get_all_sessions(
            class_group_id=class_group_id,
            session_date=session_date,
            status=status,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit,
        )
        return [self._session_to_response(s) for s in sessions]

    def create_session(self, obj_in: ClassSessionCreate) -> ClassSessionResponse:
        g = self.repo.get_group_by_id(obj_in.class_group_id)
        if not g:
            raise ResourceNotFoundException("ClassGroup", obj_in.class_group_id)

        # Check overlapping sessions for same class group
        overlapping = self.repo.check_class_group_overlap(
            class_group_id=obj_in.class_group_id,
            session_date=obj_in.session_date,
            start_time=obj_in.start_time,
            end_time=obj_in.end_time,
        )
        if overlapping:
            raise ConflictException(
                f"Class group '{g.name}' already has an active overlapping session at this time on {obj_in.session_date}."
            )

        # Check facility IDs
        if obj_in.required_facility_ids:
            found = self.db.scalars(
                select(Facility.id).where(Facility.id.in_(obj_in.required_facility_ids))
            ).all()
            missing = set(obj_in.required_facility_ids) - set(found)
            if missing:
                raise ValidationBusinessException(f"Facilities with IDs {list(missing)} do not exist.")

        sess = self.repo.create_session(obj_in)
        return self._session_to_response(sess)

    def update_session(self, session_id: int, obj_in: ClassSessionUpdate) -> ClassSessionResponse:
        sess = self.repo.get_session_by_id(session_id)
        if not sess:
            raise ResourceNotFoundException("ClassSession", session_id)

        target_group_id = obj_in.class_group_id or sess.class_group_id
        target_date = obj_in.session_date or sess.session_date
        target_start = obj_in.start_time or sess.start_time
        target_end = obj_in.end_time or sess.end_time
        target_status = obj_in.status or sess.status

        if target_status == "ACTIVE" and (
            obj_in.session_date or obj_in.start_time or obj_in.end_time or obj_in.class_group_id
        ):
            overlapping = self.repo.check_class_group_overlap(
                class_group_id=target_group_id,
                session_date=target_date,
                start_time=target_start,
                end_time=target_end,
                exclude_session_id=session_id,
            )
            if overlapping:
                raise ConflictException(
                    "Class group already has an active overlapping session at the requested time."
                )

        updated = self.repo.update_session(sess, obj_in)
        return self._session_to_response(updated)

    def delete_session(self, session_id: int) -> None:
        deleted = self.repo.delete_session(session_id)
        if not deleted:
            raise ResourceNotFoundException("ClassSession", session_id)

    # --- Time Slots ---
    def list_time_slots(self) -> List[TimeSlotResponse]:
        slots = self.repo.get_time_slots()
        return [TimeSlotResponse.model_validate(s) for s in slots]

    def create_time_slot(self, obj_in: TimeSlotCreate) -> TimeSlotResponse:
        slot = self.repo.create_time_slot(obj_in)
        return TimeSlotResponse.model_validate(slot)

