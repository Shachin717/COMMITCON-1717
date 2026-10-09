from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.classroom import Classroom
from app.models.facility import Facility
from app.models.department import Department
from app.models.room_department_access import RoomDepartmentAccess
from app.schemas.classroom import (
    ClassroomCreate,
    ClassroomUpdate,
    ClassroomResponse,
    FacilityResponse,
    BuildingResponse,
)
from app.repositories.classroom_repository import ClassroomRepository
from app.core.exceptions import (
    ResourceNotFoundException,
    ValidationBusinessException,
    ConflictException,
)


class ClassroomService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ClassroomRepository(db)

    def _to_response(self, room: Classroom) -> ClassroomResponse:
        fac_responses = [
            FacilityResponse(
                id=cf.facility.id,
                name=cf.facility.name,
                description=cf.facility.description,
            )
            for cf in room.facilities
            if cf.facility
        ]
        b_resp = (
            BuildingResponse(id=room.building.id, name=room.building.name, location=room.building.location)
            if room.building
            else None
        )
        auth_dept_ids = (
            [da.department_id for da in room.department_accesses]
            if room.room_type == "LAB"
            else []
        )
        return ClassroomResponse(
            id=room.id,
            name=room.name,
            building_id=room.building_id,
            capacity=room.capacity,
            room_type=room.room_type,
            location_description=room.location_description,
            is_active=room.is_active,
            created_at=room.created_at,
            updated_at=room.updated_at,
            building=b_resp,
            facilities=fac_responses,
            authorized_department_ids=auth_dept_ids,
        )

    def get_classroom(self, room_id: int) -> ClassroomResponse:
        room = self.repo.get_by_id(room_id)
        if not room:
            raise ResourceNotFoundException("Classroom", room_id)
        return self._to_response(room)

    def list_classrooms(
        self,
        room_type: Optional[str] = None,
        min_capacity: Optional[int] = None,
        building_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        facility_ids: Optional[List[int]] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ClassroomResponse]:
        rooms = self.repo.get_all(
            room_type=room_type,
            min_capacity=min_capacity,
            building_id=building_id,
            is_active=is_active,
            facility_ids=facility_ids,
            skip=skip,
            limit=limit,
        )
        return [self._to_response(r) for r in rooms]

    def create_classroom(self, obj_in: ClassroomCreate) -> ClassroomResponse:
        if obj_in.capacity <= 0:
            raise ValidationBusinessException("Room capacity must be a positive integer.")
        if obj_in.room_type not in ("CLASSROOM", "LAB"):
            raise ValidationBusinessException(f"Invalid room type: {obj_in.room_type}. Must be CLASSROOM or LAB.")

        # Check duplicate room name within the same building
        existing = self.db.scalars(
            select(Classroom).where(Classroom.name == obj_in.name, Classroom.building_id == obj_in.building_id)
        ).first()
        if existing:
            raise ConflictException(f"A room named '{obj_in.name}' already exists in this building.")

        # Validate that facility_ids exist
        if obj_in.facility_ids:
            found_facs = self.db.scalars(
                select(Facility.id).where(Facility.id.in_(obj_in.facility_ids))
            ).all()
            missing = set(obj_in.facility_ids) - set(found_facs)
            if missing:
                raise ValidationBusinessException(f"Facilities with IDs {list(missing)} do not exist.")

        room = self.repo.create(obj_in)
        return self._to_response(room)

    def update_classroom(self, room_id: int, obj_in: ClassroomUpdate) -> ClassroomResponse:
        room = self.repo.get_by_id(room_id)
        if not room:
            raise ResourceNotFoundException("Classroom", room_id)

        if obj_in.capacity is not None and obj_in.capacity <= 0:
            raise ValidationBusinessException("Room capacity must be a positive integer.")

        # If changing from LAB to CLASSROOM, check existing department accesses
        if obj_in.room_type and obj_in.room_type != room.room_type:
            if obj_in.room_type == "CLASSROOM" and room.room_type == "LAB":
                # Clear department access mappings
                self.repo.set_lab_department_access(room_id, [])

        updated = self.repo.update(room, obj_in)
        return self._to_response(updated)

    def delete_classroom(self, room_id: int) -> None:
        room = self.repo.get_by_id(room_id)
        if not room:
            raise ResourceNotFoundException("Classroom", room_id)
        self.repo.delete(room_id)

    # --- Lab Department Access ---
    def set_lab_department_access(self, room_id: int, department_ids: List[int]) -> List[int]:
        room = self.repo.get_by_id(room_id)
        if not room:
            raise ResourceNotFoundException("Classroom", room_id)

        # Reject if room is regular classroom
        if room.room_type != "LAB":
            raise ValidationBusinessException(
                f"Cannot configure department access for room '{room.name}' because its room_type is CLASSROOM. "
                f"Department access restrictions only apply to LABs."
            )

        # Validate that all department IDs exist
        if department_ids:
            found_depts = self.db.scalars(
                select(Department.id).where(Department.id.in_(department_ids))
            ).all()
            missing = set(department_ids) - set(found_depts)
            if missing:
                raise ValidationBusinessException(f"Departments with IDs {list(missing)} do not exist.")

        return self.repo.set_lab_department_access(room_id, department_ids)

    def get_lab_department_access(self, room_id: int) -> List[int]:
        room = self.repo.get_by_id(room_id)
        if not room:
            raise ResourceNotFoundException("Classroom", room_id)
        if room.room_type != "LAB":
            raise ValidationBusinessException(
                f"Room '{room.name}' is a CLASSROOM. Department access restrictions only apply to LABs."
            )
        return [da.department_id for da in room.department_accesses]

    # --- Facilities Management ---
    def add_facility_to_room(self, room_id: int, facility_id: int) -> ClassroomResponse:
        room = self.repo.get_by_id(room_id)
        if not room:
            raise ResourceNotFoundException("Classroom", room_id)
        fac = self.db.get(Facility, facility_id)
        if not fac:
            raise ResourceNotFoundException("Facility", facility_id)
        self.repo.add_facility(room_id, facility_id)
        return self.get_classroom(room_id)

    def remove_facility_from_room(self, room_id: int, facility_id: int) -> ClassroomResponse:
        room = self.repo.get_by_id(room_id)
        if not room:
            raise ResourceNotFoundException("Classroom", room_id)
        self.repo.remove_facility(room_id, facility_id)
        return self.get_classroom(room_id)

