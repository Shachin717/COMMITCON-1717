from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.department import Department
from app.models.building import Building
from app.models.facility import Facility
from app.models.class_group import ClassGroup
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.schemas.building import BuildingCreate, BuildingUpdate
from app.schemas.facility import FacilityCreate, FacilityUpdate
from app.core.exceptions import ResourceNotFoundException, ConflictException, ValidationBusinessException


class DepartmentService:
    def __init__(self, db: Session):
        self.db = db

    # --- Department ---
    def get_department(self, dept_id: int) -> Department:
        dept = self.db.get(Department, dept_id)
        if not dept:
            raise ResourceNotFoundException("Department", dept_id)
        return dept

    def list_departments(self) -> List[Department]:
        return list(self.db.scalars(select(Department).order_by(Department.name)).all())

    def create_department(self, obj_in: DepartmentCreate) -> Department:
        # Check duplicate name or code
        existing = self.db.scalars(
            select(Department).where((Department.name == obj_in.name) | (Department.code == obj_in.code))
        ).first()
        if existing:
            if existing.name == obj_in.name:
                raise ConflictException(f"Department with name '{obj_in.name}' already exists.")
            raise ConflictException(f"Department with code '{obj_in.code}' already exists.")

        dept = Department(name=obj_in.name, code=obj_in.code)
        self.db.add(dept)
        self.db.commit()
        self.db.refresh(dept)
        return dept

    def update_department(self, dept_id: int, obj_in: DepartmentUpdate) -> Department:
        dept = self.get_department(dept_id)
        if obj_in.name and obj_in.name != dept.name:
            if self.db.scalars(select(Department).where(Department.name == obj_in.name, Department.id != dept_id)).first():
                raise ConflictException(f"Department name '{obj_in.name}' is already taken.")
            dept.name = obj_in.name
        if obj_in.code and obj_in.code != dept.code:
            if self.db.scalars(select(Department).where(Department.code == obj_in.code, Department.id != dept_id)).first():
                raise ConflictException(f"Department code '{obj_in.code}' is already taken.")
            dept.code = obj_in.code

        self.db.commit()
        self.db.refresh(dept)
        return dept

    def delete_department(self, dept_id: int) -> None:
        dept = self.get_department(dept_id)
        # Check if department has class groups
        groups_count = self.db.scalars(select(ClassGroup).where(ClassGroup.department_id == dept_id)).all()
        if groups_count:
            raise ValidationBusinessException(
                f"Cannot delete department '{dept.name}' because it contains {len(groups_count)} class groups."
            )
        self.db.delete(dept)
        self.db.commit()

    # --- Buildings ---
    def get_building(self, building_id: int) -> Building:
        b = self.db.get(Building, building_id)
        if not b:
            raise ResourceNotFoundException("Building", building_id)
        return b

    def list_buildings(self) -> List[Building]:
        return list(self.db.scalars(select(Building).order_by(Building.name)).all())

    def create_building(self, obj_in: BuildingCreate) -> Building:
        existing = self.db.scalars(select(Building).where(Building.name == obj_in.name)).first()
        if existing:
            raise ConflictException(f"Building with name '{obj_in.name}' already exists.")
        b = Building(name=obj_in.name, location=obj_in.location)
        self.db.add(b)
        self.db.commit()
        self.db.refresh(b)
        return b

    def update_building(self, building_id: int, obj_in: BuildingUpdate) -> Building:
        b = self.get_building(building_id)
        if obj_in.name and obj_in.name != b.name:
            if self.db.scalars(select(Building).where(Building.name == obj_in.name, Building.id != building_id)).first():
                raise ConflictException(f"Building name '{obj_in.name}' is already taken.")
            b.name = obj_in.name
        if obj_in.location is not None:
            b.location = obj_in.location
        self.db.commit()
        self.db.refresh(b)
        return b

    def delete_building(self, building_id: int) -> None:
        b = self.get_building(building_id)
        self.db.delete(b)
        self.db.commit()

    # --- Facilities ---
    def get_facility(self, facility_id: int) -> Facility:
        f = self.db.get(Facility, facility_id)
        if not f:
            raise ResourceNotFoundException("Facility", facility_id)
        return f

    def list_facilities(self) -> List[Facility]:
        return list(self.db.scalars(select(Facility).order_by(Facility.name)).all())

    def create_facility(self, obj_in: FacilityCreate) -> Facility:
        existing = self.db.scalars(select(Facility).where(Facility.name == obj_in.name)).first()
        if existing:
            raise ConflictException(f"Facility with name '{obj_in.name}' already exists.")
        f = Facility(name=obj_in.name, description=obj_in.description)
        self.db.add(f)
        self.db.commit()
        self.db.refresh(f)
        return f

