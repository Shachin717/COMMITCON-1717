from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, delete
from app.models.classroom import Classroom
from app.models.classroom_facility import ClassroomFacility
from app.models.room_department_access import RoomDepartmentAccess
from app.models.facility import Facility
from app.schemas.classroom import ClassroomCreate, ClassroomUpdate


class ClassroomRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, room_id: int) -> Optional[Classroom]:
        stmt = (
            select(Classroom)
            .options(
                joinedload(Classroom.building),
                joinedload(Classroom.facilities).joinedload(ClassroomFacility.facility),
                joinedload(Classroom.department_accesses),
            )
            .where(Classroom.id == room_id)
        )
        return self.db.scalars(stmt).unique().first()

    def get_all(
        self,
        room_type: Optional[str] = None,
        min_capacity: Optional[int] = None,
        building_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        facility_ids: Optional[List[int]] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Classroom]:
        stmt = (
            select(Classroom)
            .options(
                joinedload(Classroom.building),
                joinedload(Classroom.facilities).joinedload(ClassroomFacility.facility),
                joinedload(Classroom.department_accesses),
            )
        )
        if room_type:
            stmt = stmt.where(Classroom.room_type == room_type)
        if min_capacity is not None:
            stmt = stmt.where(Classroom.capacity >= min_capacity)
        if building_id is not None:
            stmt = stmt.where(Classroom.building_id == building_id)
        if is_active is not None:
            stmt = stmt.where(Classroom.is_active == is_active)

        results = self.db.scalars(stmt).unique().all()

        # If facility_ids filter specified, ensure room has ALL requested facilities
        if facility_ids:
            filtered = []
            target_ids = set(facility_ids)
            for r in results:
                room_fac_ids = {cf.facility_id for cf in r.facilities}
                if target_ids.issubset(room_fac_ids):
                    filtered.append(r)
            results = filtered

        return results[skip : skip + limit]

    def create(self, obj_in: ClassroomCreate) -> Classroom:
        db_obj = Classroom(
            name=obj_in.name,
            building_id=obj_in.building_id,
            capacity=obj_in.capacity,
            room_type=obj_in.room_type,
            location_description=obj_in.location_description,
            is_active=obj_in.is_active,
        )
        self.db.add(db_obj)
        self.db.flush()

        if obj_in.facility_ids:
            for fac_id in set(obj_in.facility_ids):
                self.db.add(ClassroomFacility(classroom_id=db_obj.id, facility_id=fac_id))
            self.db.flush()

        self.db.commit()
        return self.get_by_id(db_obj.id)

    def update(self, db_obj: Classroom, obj_in: ClassroomUpdate) -> Classroom:
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        self.db.commit()
        return self.get_by_id(db_obj.id)

    def delete(self, room_id: int) -> bool:
        db_obj = self.get_by_id(room_id)
        if not db_obj:
            return False
        self.db.delete(db_obj)
        self.db.commit()
        return True

    def set_lab_department_access(self, room_id: int, department_ids: List[int]) -> List[int]:
        # Clear existing access
        self.db.execute(delete(RoomDepartmentAccess).where(RoomDepartmentAccess.room_id == room_id))
        self.db.flush()
        # Add new
        for dept_id in set(department_ids):
            self.db.add(RoomDepartmentAccess(room_id=room_id, department_id=dept_id))
        self.db.commit()
        return list(set(department_ids))

    def add_facility(self, room_id: int, facility_id: int) -> bool:
        stmt = select(ClassroomFacility).where(
            ClassroomFacility.classroom_id == room_id, ClassroomFacility.facility_id == facility_id
        )
        existing = self.db.scalars(stmt).first()
        if not existing:
            self.db.add(ClassroomFacility(classroom_id=room_id, facility_id=facility_id))
            self.db.commit()
        return True

    def remove_facility(self, room_id: int, facility_id: int) -> bool:
        stmt = delete(ClassroomFacility).where(
            ClassroomFacility.classroom_id == room_id, ClassroomFacility.facility_id == facility_id
        )
        self.db.execute(stmt)
        self.db.commit()
        return True

