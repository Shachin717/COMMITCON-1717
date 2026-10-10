import csv
import io
import math
import secrets
import string
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.block import Block, BlockCoordinator
from app.models.booking import Booking
from app.models.department import Department
from app.models.enums import BookingStatus, RequesterType, RoomStatus, RoomType, UserRole
from app.models.facility import Facility
from app.models.room import Room
from app.models.time_slot import TimeSlot
from app.models.timetable import TimetableEntry
from app.models.user import User
from app.schemas.block import BlockCreate, BlockUpdate
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.schemas.facility import FacilityCreate, FacilityUpdate
from app.schemas.overview import (
    AdminOverviewResponse,
    DailyBookingStats,
    RoomTypeUsageStats,
)
from app.schemas.room import RoomCreate, RoomImportResponse, RoomUpdate
from app.schemas.time_slot import TimeSlotCreate, TimeSlotUpdate
from app.schemas.timetable import (
    TimetableEntryCreate,
    TimetableEntryUpdate,
    TimetableImportResponse,
)
from app.schemas.user import AdminUserCreate, UserUpdate
from app.services.audit import log_audit
from app.services.email import send_user_welcome_email



# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------

def _generate_temp_password(length: int = 12) -> str:
    """Generate a secure, random temporary password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in "!@#$%&*" for pwd_c in pwd for c in pwd_c)
        ):
            return pwd


DAY_NAME_TO_INT = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}


# ---------------------------------------------------------
# User Service
# ---------------------------------------------------------

def create_admin_user(
    db: Session, data: AdminUserCreate, actor_id: int
) -> Tuple[User, str]:
    """
    Create a staff user (HOD, COORDINATOR, FACULTY, or ADMIN) with an auto-generated
    temporary password and email delivery.
    """
    email_clean = data.email.lower().strip()
    existing = db.query(User).filter(func.lower(User.email) == email_clean).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{data.email}' already exists",
        )

    if data.department_id:
        dept = db.query(Department).filter(Department.id == data.department_id).first()
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with ID {data.department_id} not found",
            )

    temp_password = _generate_temp_password(12)
    pwd_hash = hash_password(temp_password)

    user = User(
        name=data.name.strip(),
        email=email_clean,
        password_hash=pwd_hash,
        role=data.role,
        department_id=data.department_id,
        phone=data.phone.strip() if data.phone else None,
        is_active=True,
        must_change_password=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Email credentials
    send_user_welcome_email(
        to_email=user.email,
        user_name=user.name,
        role=user.role.value,
        temp_password=temp_password,
    )

    log_audit(
        db,
        action="USER_CREATED",
        entity="User",
        entity_id=str(user.id),
        actor_id=actor_id,
        meta={"email": user.email, "role": user.role.value},
    )

    return user, temp_password


def list_users(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    role: Optional[UserRole] = None,
    department_id: Optional[int] = None,
    is_active: Optional[bool] = None,
) -> Tuple[List[User], int]:
    """List users with pagination, search, and filtering."""
    query = db.query(User)

    if search:
        search_term = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(User.name).ilike(search_term),
                func.lower(User.email).ilike(search_term),
                func.lower(User.phone).ilike(search_term),
            )
        )
    if role is not None:
        query = query.filter(User.role == role)
    if department_id is not None:
        query = query.filter(User.department_id == department_id)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    total = query.count()
    users = (
        query.order_by(User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return users, total


def get_user_by_id(db: Session, user_id: int) -> User:
    """Retrieve user by ID or raise 404."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )
    return user


def update_user(
    db: Session, user_id: int, data: UserUpdate, actor_id: int
) -> User:
    """Update user attributes."""
    user = get_user_by_id(db, user_id)

    if data.email is not None:
        email_clean = data.email.lower().strip()
        if email_clean != user.email:
            existing = (
                db.query(User).filter(func.lower(User.email) == email_clean).first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Email '{data.email}' is already in use by another user",
                )
            user.email = email_clean

    if data.department_id is not None:
        dept = db.query(Department).filter(Department.id == data.department_id).first()
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with ID {data.department_id} not found",
            )
        user.department_id = data.department_id

    if data.name is not None:
        user.name = data.name.strip()
    if data.role is not None:
        user.role = data.role
    if data.phone is not None:
        user.phone = data.phone.strip() if data.phone else None
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.must_change_password is not None:
        user.must_change_password = data.must_change_password
    if data.password is not None:
        user.password_hash = hash_password(data.password)

    db.commit()
    db.refresh(user)

    log_audit(
        db,
        action="USER_UPDATED",
        entity="User",
        entity_id=str(user.id),
        actor_id=actor_id,
        meta={"email": user.email, "role": user.role.value},
    )

    return user


def set_user_active_status(
    db: Session, user_id: int, is_active: bool, actor_id: int
) -> User:
    """Activate or deactivate a user account."""
    user = get_user_by_id(db, user_id)
    user.is_active = is_active
    db.commit()
    db.refresh(user)

    log_audit(
        db,
        action="USER_ACTIVATED" if is_active else "USER_DEACTIVATED",
        entity="User",
        entity_id=str(user.id),
        actor_id=actor_id,
        meta={"email": user.email, "is_active": is_active},
    )

    return user


# ---------------------------------------------------------
# Department Service
# ---------------------------------------------------------

def create_department(
    db: Session, data: DepartmentCreate, actor_id: int
) -> Department:
    """Create a new department."""
    code_clean = data.code.strip().upper()
    existing = (
        db.query(Department).filter(func.upper(Department.code) == code_clean).first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Department with code '{data.code}' already exists",
        )

    dept = Department(
        name=data.name.strip(),
        code=code_clean,
        hod_approval_required=data.hod_approval_required,
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)

    log_audit(
        db,
        action="DEPARTMENT_CREATED",
        entity="Department",
        entity_id=str(dept.id),
        actor_id=actor_id,
        meta={"name": dept.name, "code": dept.code},
    )

    return dept


def list_departments(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    hod_approval_required: Optional[bool] = None,
) -> Tuple[List[Department], int]:
    """List departments with pagination and search."""
    query = db.query(Department)

    if search:
        search_term = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Department.name).ilike(search_term),
                func.lower(Department.code).ilike(search_term),
            )
        )
    if hod_approval_required is not None:
        query = query.filter(
            Department.hod_approval_required == hod_approval_required
        )

    total = query.count()
    depts = (
        query.order_by(Department.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return depts, total


def get_department_by_id(db: Session, department_id: int) -> Department:
    """Get department by ID or raise 404."""
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {department_id} not found",
        )
    return dept


def update_department(
    db: Session, department_id: int, data: DepartmentUpdate, actor_id: int
) -> Department:
    """Update department attributes."""
    dept = get_department_by_id(db, department_id)

    if data.code is not None:
        code_clean = data.code.strip().upper()
        if code_clean != dept.code:
            existing = (
                db.query(Department)
                .filter(func.upper(Department.code) == code_clean)
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Department code '{data.code}' already exists",
                )
            dept.code = code_clean

    if data.name is not None:
        dept.name = data.name.strip()
    if data.hod_approval_required is not None:
        dept.hod_approval_required = data.hod_approval_required

    db.commit()
    db.refresh(dept)

    log_audit(
        db,
        action="DEPARTMENT_UPDATED",
        entity="Department",
        entity_id=str(dept.id),
        actor_id=actor_id,
        meta={"code": dept.code, "hod_approval_required": dept.hod_approval_required},
    )

    return dept


def toggle_department_hod_approval(
    db: Session, department_id: int, actor_id: int
) -> Department:
    """Toggle hod_approval_required setting for a department."""
    dept = get_department_by_id(db, department_id)
    dept.hod_approval_required = not dept.hod_approval_required
    db.commit()
    db.refresh(dept)

    log_audit(
        db,
        action="DEPARTMENT_HOD_APPROVAL_TOGGLED",
        entity="Department",
        entity_id=str(dept.id),
        actor_id=actor_id,
        meta={"code": dept.code, "hod_approval_required": dept.hod_approval_required},
    )

    return dept


def delete_department(db: Session, department_id: int, actor_id: int) -> None:
    """Delete a department."""
    dept = get_department_by_id(db, department_id)
    code = dept.code
    db.delete(dept)
    db.commit()

    log_audit(
        db,
        action="DEPARTMENT_DELETED",
        entity="Department",
        entity_id=str(department_id),
        actor_id=actor_id,
        meta={"code": code},
    )


# ---------------------------------------------------------
# Block Service
# ---------------------------------------------------------

def create_block(db: Session, data: BlockCreate, actor_id: int) -> Block:
    """Create a new physical block."""
    name_clean = data.name.strip()
    existing = db.query(Block).filter(func.lower(Block.name) == name_clean.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Block with name '{data.name}' already exists",
        )

    block = Block(
        name=name_clean,
        description=data.description.strip() if data.description else None,
    )
    db.add(block)
    db.commit()
    db.refresh(block)

    log_audit(
        db,
        action="BLOCK_CREATED",
        entity="Block",
        entity_id=str(block.id),
        actor_id=actor_id,
        meta={"name": block.name},
    )

    return block


def list_blocks(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
) -> Tuple[List[Block], int]:
    """List blocks with assigned coordinators."""
    query = db.query(Block).options(joinedload(Block.coordinators))

    if search:
        search_term = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Block.name).ilike(search_term),
                func.lower(Block.description).ilike(search_term),
            )
        )

    total = query.count()
    blocks = (
        query.order_by(Block.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return blocks, total


def get_block_by_id(db: Session, block_id: int) -> Block:
    """Retrieve block with coordinators."""
    block = (
        db.query(Block)
        .options(joinedload(Block.coordinators))
        .filter(Block.id == block_id)
        .first()
    )
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Block with ID {block_id} not found",
        )
    return block


def update_block(
    db: Session, block_id: int, data: BlockUpdate, actor_id: int
) -> Block:
    """Update block details."""
    block = get_block_by_id(db, block_id)

    if data.name is not None:
        name_clean = data.name.strip()
        if name_clean.lower() != block.name.lower():
            existing = (
                db.query(Block)
                .filter(func.lower(Block.name) == name_clean.lower())
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Block with name '{data.name}' already exists",
                )
            block.name = name_clean

    if data.description is not None:
        block.description = data.description.strip() if data.description else None

    db.commit()
    db.refresh(block)

    log_audit(
        db,
        action="BLOCK_UPDATED",
        entity="Block",
        entity_id=str(block.id),
        actor_id=actor_id,
        meta={"name": block.name},
    )

    return block


def delete_block(db: Session, block_id: int, actor_id: int) -> None:
    """Delete a block."""
    block = get_block_by_id(db, block_id)
    name = block.name
    db.delete(block)
    db.commit()

    log_audit(
        db,
        action="BLOCK_DELETED",
        entity="Block",
        entity_id=str(block_id),
        actor_id=actor_id,
        meta={"name": name},
    )


def assign_coordinator_to_block(
    db: Session, block_id: int, user_id: int, actor_id: int
) -> Block:
    """Assign a coordinator to a block."""
    block = get_block_by_id(db, block_id)
    user = get_user_by_id(db, user_id)

    if user.role not in (UserRole.COORDINATOR, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User {user.email} does not have COORDINATOR role (current role: {user.role.value})",
        )

    existing_assignment = (
        db.query(BlockCoordinator)
        .filter(
            BlockCoordinator.block_id == block_id,
            BlockCoordinator.user_id == user_id,
        )
        .first()
    )
    if existing_assignment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Coordinator '{user.name}' is already assigned to block '{block.name}'",
        )

    assignment = BlockCoordinator(block_id=block_id, user_id=user_id)
    db.add(assignment)
    db.commit()
    db.refresh(block)

    log_audit(
        db,
        action="COORDINATOR_ASSIGNED",
        entity="Block",
        entity_id=str(block_id),
        actor_id=actor_id,
        meta={"block_id": block_id, "user_id": user_id, "user_email": user.email},
    )

    return block


def unassign_coordinator_from_block(
    db: Session, block_id: int, user_id: int, actor_id: int
) -> Block:
    """Unassign a coordinator from a block."""
    block = get_block_by_id(db, block_id)
    assignment = (
        db.query(BlockCoordinator)
        .filter(
            BlockCoordinator.block_id == block_id,
            BlockCoordinator.user_id == user_id,
        )
        .first()
    )
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} is not assigned to block {block_id}",
        )

    db.delete(assignment)
    db.commit()
    db.refresh(block)

    log_audit(
        db,
        action="COORDINATOR_UNASSIGNED",
        entity="Block",
        entity_id=str(block_id),
        actor_id=actor_id,
        meta={"block_id": block_id, "user_id": user_id},
    )

    return block


# ---------------------------------------------------------
# Facility Service
# ---------------------------------------------------------

def create_facility(
    db: Session, data: FacilityCreate, actor_id: int
) -> Facility:
    """Create a new amenity / facility."""
    name_clean = data.name.strip()
    existing = (
        db.query(Facility)
        .filter(func.lower(Facility.name) == name_clean.lower())
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Facility '{data.name}' already exists",
        )

    facility = Facility(name=name_clean)
    db.add(facility)
    db.commit()
    db.refresh(facility)

    log_audit(
        db,
        action="FACILITY_CREATED",
        entity="Facility",
        entity_id=str(facility.id),
        actor_id=actor_id,
        meta={"name": facility.name},
    )

    return facility


def list_facilities(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
) -> Tuple[List[Facility], int]:
    """List facilities with pagination and search."""
    query = db.query(Facility)
    if search:
        search_term = f"%{search.strip().lower()}%"
        query = query.filter(func.lower(Facility.name).ilike(search_term))

    total = query.count()
    facilities = (
        query.order_by(Facility.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return facilities, total


def get_facility_by_id(db: Session, facility_id: int) -> Facility:
    """Retrieve facility by ID."""
    fac = db.query(Facility).filter(Facility.id == facility_id).first()
    if not fac:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Facility with ID {facility_id} not found",
        )
    return fac


def update_facility(
    db: Session, facility_id: int, data: FacilityUpdate, actor_id: int
) -> Facility:
    """Update facility name."""
    fac = get_facility_by_id(db, facility_id)
    if data.name is not None:
        name_clean = data.name.strip()
        if name_clean.lower() != fac.name.lower():
            existing = (
                db.query(Facility)
                .filter(func.lower(Facility.name) == name_clean.lower())
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Facility with name '{data.name}' already exists",
                )
            fac.name = name_clean

    db.commit()
    db.refresh(fac)

    log_audit(
        db,
        action="FACILITY_UPDATED",
        entity="Facility",
        entity_id=str(fac.id),
        actor_id=actor_id,
        meta={"name": fac.name},
    )

    return fac


def delete_facility(db: Session, facility_id: int, actor_id: int) -> None:
    """Delete a facility."""
    fac = get_facility_by_id(db, facility_id)
    name = fac.name
    db.delete(fac)
    db.commit()

    log_audit(
        db,
        action="FACILITY_DELETED",
        entity="Facility",
        entity_id=str(facility_id),
        actor_id=actor_id,
        meta={"name": name},
    )


# ---------------------------------------------------------
# Room Service
# ---------------------------------------------------------

def create_room(db: Session, data: RoomCreate, actor_id: int) -> Room:
    """
    Create a new room.
    Validates capacity > 0, block existence, unique name,
    and requires department_id if room_type is LAB.
    """
    # Validation: capacity
    if data.capacity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Room capacity must be greater than 0",
        )

    # Validation: LAB requires department
    if data.room_type == RoomType.LAB and not data.department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department is required for LAB rooms",
        )

    # Validation: Block exists
    block = db.query(Block).filter(Block.id == data.block_id).first()
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Block with ID {data.block_id} not found",
        )

    # Validation: Department exists if provided
    if data.department_id:
        dept = db.query(Department).filter(Department.id == data.department_id).first()
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with ID {data.department_id} not found",
            )

    # Validation: Unique room name
    name_clean = data.name.strip()
    existing = db.query(Room).filter(func.lower(Room.name) == name_clean.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Room with name '{data.name}' already exists",
        )

    room = Room(
        name=name_clean,
        block_id=data.block_id,
        floor=data.floor,
        room_type=data.room_type,
        capacity=data.capacity,
        department_id=data.department_id,
        status=data.status,
        maintenance_note=data.maintenance_note.strip() if data.maintenance_note else None,
    )

    if data.facility_ids:
        facilities = db.query(Facility).filter(Facility.id.in_(data.facility_ids)).all()
        room.facilities = facilities

    db.add(room)
    db.commit()
    db.refresh(room)

    log_audit(
        db,
        action="ROOM_CREATED",
        entity="Room",
        entity_id=str(room.id),
        actor_id=actor_id,
        meta={"name": room.name, "type": room.room_type.value, "capacity": room.capacity},
    )

    return room


def list_rooms(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    block_id: Optional[int] = None,
    department_id: Optional[int] = None,
    room_type: Optional[RoomType] = None,
    status: Optional[RoomStatus] = None,
) -> Tuple[List[Room], int]:
    """List rooms with facilities, pagination, search, and filters."""
    query = db.query(Room).options(joinedload(Room.facilities))

    if search:
        search_term = f"%{search.strip().lower()}%"
        query = query.filter(func.lower(Room.name).ilike(search_term))
    if block_id is not None:
        query = query.filter(Room.block_id == block_id)
    if department_id is not None:
        query = query.filter(Room.department_id == department_id)
    if room_type is not None:
        query = query.filter(Room.room_type == room_type)
    if status is not None:
        query = query.filter(Room.status == status)

    total = query.count()
    rooms = (
        query.order_by(Room.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return rooms, total


def get_room_by_id(db: Session, room_id: int) -> Room:
    """Retrieve room by ID with attached facilities."""
    room = (
        db.query(Room)
        .options(joinedload(Room.facilities))
        .filter(Room.id == room_id)
        .first()
    )
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {room_id} not found",
        )
    return room


def update_room(
    db: Session, room_id: int, data: RoomUpdate, actor_id: int
) -> Room:
    """Update room attributes with lab department constraints."""
    room = get_room_by_id(db, room_id)

    target_room_type = data.room_type or room.room_type
    target_dept_id = (
        data.department_id if data.department_id is not None else room.department_id
    )

    if target_room_type == RoomType.LAB and not target_dept_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department is required for LAB rooms",
        )

    if data.capacity is not None and data.capacity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Room capacity must be greater than 0",
        )

    if data.name is not None:
        name_clean = data.name.strip()
        if name_clean.lower() != room.name.lower():
            existing = (
                db.query(Room)
                .filter(func.lower(Room.name) == name_clean.lower())
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Room with name '{data.name}' already exists",
                )
            room.name = name_clean

    if data.block_id is not None:
        block = db.query(Block).filter(Block.id == data.block_id).first()
        if not block:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Block with ID {data.block_id} not found",
            )
        room.block_id = data.block_id

    if data.department_id is not None:
        dept = db.query(Department).filter(Department.id == data.department_id).first()
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with ID {data.department_id} not found",
            )
        room.department_id = data.department_id

    if data.floor is not None:
        room.floor = data.floor
    if data.room_type is not None:
        room.room_type = data.room_type
    if data.capacity is not None:
        room.capacity = data.capacity
    if data.status is not None:
        room.status = data.status
    if data.maintenance_note is not None:
        room.maintenance_note = (
            data.maintenance_note.strip() if data.maintenance_note else None
        )

    if data.facility_ids is not None:
        facilities = db.query(Facility).filter(Facility.id.in_(data.facility_ids)).all()
        room.facilities = facilities

    db.commit()
    db.refresh(room)

    log_audit(
        db,
        action="ROOM_UPDATED",
        entity="Room",
        entity_id=str(room.id),
        actor_id=actor_id,
        meta={"name": room.name, "status": room.status.value},
    )

    return room


def set_room_status(
    db: Session,
    room_id: int,
    status: RoomStatus,
    maintenance_note: Optional[str],
    actor_id: int,
) -> Room:
    """Set room status (ACTIVE / MAINTENANCE) with an optional note."""
    room = get_room_by_id(db, room_id)
    room.status = status
    if maintenance_note is not None:
        room.maintenance_note = maintenance_note.strip() if maintenance_note else None
    elif status == RoomStatus.ACTIVE:
        room.maintenance_note = None

    db.commit()
    db.refresh(room)

    log_audit(
        db,
        action="ROOM_STATUS_UPDATED",
        entity="Room",
        entity_id=str(room.id),
        actor_id=actor_id,
        meta={"name": room.name, "status": status.value, "note": room.maintenance_note},
    )

    return room


def delete_room(db: Session, room_id: int, actor_id: int) -> None:
    """Delete a room."""
    room = get_room_by_id(db, room_id)
    name = room.name
    db.delete(room)
    db.commit()

    log_audit(
        db,
        action="ROOM_DELETED",
        entity="Room",
        entity_id=str(room_id),
        actor_id=actor_id,
        meta={"name": name},
    )


# ---------------------------------------------------------
# Time Slot Service
# ---------------------------------------------------------

def create_time_slot(
    db: Session, data: TimeSlotCreate, actor_id: int
) -> TimeSlot:
    """Create a new time slot with start_time < end_time validation."""
    if data.start_time >= data.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be before end time",
        )

    slot = TimeSlot(
        label=data.label.strip(),
        start_time=data.start_time,
        end_time=data.end_time,
        order=data.order,
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)

    log_audit(
        db,
        action="TIME_SLOT_CREATED",
        entity="TimeSlot",
        entity_id=str(slot.id),
        actor_id=actor_id,
        meta={"label": slot.label, "order": slot.order},
    )

    return slot


def list_time_slots(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
) -> Tuple[List[TimeSlot], int]:
    """List time slots ordered by slot order."""
    query = db.query(TimeSlot)
    if search:
        search_term = f"%{search.strip().lower()}%"
        query = query.filter(func.lower(TimeSlot.label).ilike(search_term))

    total = query.count()
    slots = (
        query.order_by(TimeSlot.order.asc(), TimeSlot.start_time.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return slots, total


def get_time_slot_by_id(db: Session, slot_id: int) -> TimeSlot:
    """Retrieve time slot by ID."""
    slot = db.query(TimeSlot).filter(TimeSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Time slot with ID {slot_id} not found",
        )
    return slot


def update_time_slot(
    db: Session, slot_id: int, data: TimeSlotUpdate, actor_id: int
) -> TimeSlot:
    """Update time slot attributes."""
    slot = get_time_slot_by_id(db, slot_id)

    target_start = data.start_time or slot.start_time
    target_end = data.end_time or slot.end_time

    if target_start >= target_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be before end time",
        )

    if data.label is not None:
        slot.label = data.label.strip()
    if data.start_time is not None:
        slot.start_time = data.start_time
    if data.end_time is not None:
        slot.end_time = data.end_time
    if data.order is not None:
        slot.order = data.order

    db.commit()
    db.refresh(slot)

    log_audit(
        db,
        action="TIME_SLOT_UPDATED",
        entity="TimeSlot",
        entity_id=str(slot.id),
        actor_id=actor_id,
        meta={"label": slot.label, "order": slot.order},
    )

    return slot


def delete_time_slot(db: Session, slot_id: int, actor_id: int) -> None:
    """Delete a time slot."""
    slot = get_time_slot_by_id(db, slot_id)
    label = slot.label
    db.delete(slot)
    db.commit()

    log_audit(
        db,
        action="TIME_SLOT_DELETED",
        entity="TimeSlot",
        entity_id=str(slot_id),
        actor_id=actor_id,
        meta={"label": label},
    )


# ---------------------------------------------------------
# Timetable Entry Service
# ---------------------------------------------------------

def create_timetable_entry(
    db: Session, data: TimetableEntryCreate, actor_id: int
) -> TimetableEntry:
    """
    Create a fixed recurring timetable entry.
    Validates day_of_week in 0..6, foreign keys, and prevents slot conflicts.
    """
    if not (0 <= data.day_of_week <= 6):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="day_of_week must be between 0 (Monday) and 6 (Sunday)",
        )

    # Validate room
    room = db.query(Room).filter(Room.id == data.room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {data.room_id} not found",
        )

    # Validate slot
    slot = db.query(TimeSlot).filter(TimeSlot.id == data.slot_id).first()
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Time slot with ID {data.slot_id} not found",
        )

    # Validate department
    dept = db.query(Department).filter(Department.id == data.department_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {data.department_id} not found",
        )

    # Check unique constraint (room_id, day_of_week, slot_id)
    conflict = (
        db.query(TimetableEntry)
        .filter(
            TimetableEntry.room_id == data.room_id,
            TimetableEntry.day_of_week == data.day_of_week,
            TimetableEntry.slot_id == data.slot_id,
        )
        .first()
    )
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Room {room.name} already has timetable entry for day {data.day_of_week} at this slot ('{conflict.subject}')",
        )

    entry = TimetableEntry(
        room_id=data.room_id,
        day_of_week=data.day_of_week,
        slot_id=data.slot_id,
        department_id=data.department_id,
        subject=data.subject.strip(),
        faculty_name=data.faculty_name.strip(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    log_audit(
        db,
        action="TIMETABLE_ENTRY_CREATED",
        entity="TimetableEntry",
        entity_id=str(entry.id),
        actor_id=actor_id,
        meta={
            "room_id": entry.room_id,
            "day": entry.day_of_week,
            "slot_id": entry.slot_id,
            "subject": entry.subject,
        },
    )

    return entry


def list_timetable_entries(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    room_id: Optional[int] = None,
    day_of_week: Optional[int] = None,
    slot_id: Optional[int] = None,
    department_id: Optional[int] = None,
) -> Tuple[List[TimetableEntry], int]:
    """List timetable entries with filters and search."""
    query = db.query(TimetableEntry)

    if search:
        search_term = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(TimetableEntry.subject).ilike(search_term),
                func.lower(TimetableEntry.faculty_name).ilike(search_term),
            )
        )
    if room_id is not None:
        query = query.filter(TimetableEntry.room_id == room_id)
    if day_of_week is not None:
        query = query.filter(TimetableEntry.day_of_week == day_of_week)
    if slot_id is not None:
        query = query.filter(TimetableEntry.slot_id == slot_id)
    if department_id is not None:
        query = query.filter(TimetableEntry.department_id == department_id)

    total = query.count()
    entries = (
        query.order_by(
            TimetableEntry.day_of_week.asc(),
            TimetableEntry.slot_id.asc(),
            TimetableEntry.id.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return entries, total


def get_timetable_entry_by_id(db: Session, entry_id: int) -> TimetableEntry:
    """Retrieve timetable entry by ID."""
    entry = db.query(TimetableEntry).filter(TimetableEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Timetable entry with ID {entry_id} not found",
        )
    return entry


def update_timetable_entry(
    db: Session, entry_id: int, data: TimetableEntryUpdate, actor_id: int
) -> TimetableEntry:
    """Update timetable entry with conflict verification."""
    entry = get_timetable_entry_by_id(db, entry_id)

    target_room_id = data.room_id or entry.room_id
    target_day = data.day_of_week if data.day_of_week is not None else entry.day_of_week
    target_slot_id = data.slot_id or entry.slot_id

    if not (0 <= target_day <= 6):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="day_of_week must be between 0 (Monday) and 6 (Sunday)",
        )

    # If slot/room/day changed, check conflict
    if (
        target_room_id != entry.room_id
        or target_day != entry.day_of_week
        or target_slot_id != entry.slot_id
    ):
        conflict = (
            db.query(TimetableEntry)
            .filter(
                TimetableEntry.room_id == target_room_id,
                TimetableEntry.day_of_week == target_day,
                TimetableEntry.slot_id == target_slot_id,
                TimetableEntry.id != entry_id,
            )
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Slot conflict for room {target_room_id} on day {target_day} at slot {target_slot_id}",
            )

    if data.room_id is not None:
        if not db.query(Room).filter(Room.id == data.room_id).first():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Room with ID {data.room_id} not found",
            )
        entry.room_id = data.room_id

    if data.slot_id is not None:
        if not db.query(TimeSlot).filter(TimeSlot.id == data.slot_id).first():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Time slot with ID {data.slot_id} not found",
            )
        entry.slot_id = data.slot_id

    if data.department_id is not None:
        if not db.query(Department).filter(Department.id == data.department_id).first():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with ID {data.department_id} not found",
            )
        entry.department_id = data.department_id

    if data.day_of_week is not None:
        entry.day_of_week = data.day_of_week
    if data.subject is not None:
        entry.subject = data.subject.strip()
    if data.faculty_name is not None:
        entry.faculty_name = data.faculty_name.strip()

    db.commit()
    db.refresh(entry)

    log_audit(
        db,
        action="TIMETABLE_ENTRY_UPDATED",
        entity="TimetableEntry",
        entity_id=str(entry.id),
        actor_id=actor_id,
        meta={"subject": entry.subject, "room_id": entry.room_id},
    )

    return entry


def delete_timetable_entry(db: Session, entry_id: int, actor_id: int) -> None:
    """Delete a timetable entry."""
    entry = get_timetable_entry_by_id(db, entry_id)
    subject = entry.subject
    db.delete(entry)
    db.commit()

    log_audit(
        db,
        action="TIMETABLE_ENTRY_DELETED",
        entity="TimetableEntry",
        entity_id=str(entry_id),
        actor_id=actor_id,
        meta={"subject": subject},
    )


def import_timetable_csv(
    db: Session, csv_content: str, actor_id: int
) -> TimetableImportResponse:
    """
    Import timetable entries from CSV text.
    Supports columns: room_id (or room), day_of_week (or day), slot_id (or slot),
    department_id (or department), subject, faculty_name.
    Gracefully handles names/codes or integer IDs.
    """
    reader = csv.DictReader(io.StringIO(csv_content.strip()))
    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty or missing header line",
        )

    # Normalize header mapping
    field_map = {f.strip().lower(): f for f in reader.fieldnames if f}

    def _get_val(row: Dict[str, str], *aliases: str) -> Optional[str]:
        for alias in aliases:
            for k in row:
                if k.strip().lower() == alias:
                    val = row[k]
                    return val.strip() if val else None
        return None

    total_rows = 0
    imported = 0
    errors: List[Dict[str, Any]] = []

    # Cache lookups
    all_rooms = {r.name.lower(): r.id for r in db.query(Room).all()}
    all_rooms_by_id = {r.id: r.id for r in db.query(Room).all()}
    all_depts = {d.code.upper(): d.id for d in db.query(Department).all()}
    all_depts_by_id = {d.id: d.id for d in db.query(Department).all()}
    all_slots = {s.order: s.id for s in db.query(TimeSlot).all()}
    all_slots_by_id = {s.id: s.id for s in db.query(TimeSlot).all()}

    for row_idx, row in enumerate(reader, start=2):
        total_rows += 1
        room_raw = _get_val(row, "room_id", "room", "room_name")
        day_raw = _get_val(row, "day_of_week", "day", "day_name")
        slot_raw = _get_val(row, "slot_id", "slot", "time_slot", "slot_order")
        dept_raw = _get_val(row, "department_id", "department", "dept", "dept_code")
        subject = _get_val(row, "subject", "course", "subject_name")
        faculty = _get_val(row, "faculty_name", "faculty", "instructor")

        if not all([room_raw, day_raw, slot_raw, dept_raw, subject, faculty]):
            errors.append({
                "row": row_idx,
                "error": "Missing required fields (need room, day, slot, department, subject, faculty)",
            })
            continue

        # Resolve Room
        room_id: Optional[int] = None
        if room_raw.isdigit():
            room_id = all_rooms_by_id.get(int(room_raw))
        if room_id is None:
            room_id = all_rooms.get(room_raw.lower())
        if room_id is None:
            errors.append({"row": row_idx, "error": f"Unknown room: '{room_raw}'"})
            continue

        # Resolve Day
        day_of_week: Optional[int] = None
        if day_raw.isdigit():
            day_val = int(day_raw)
            if 0 <= day_val <= 6:
                day_of_week = day_val
        elif day_raw.lower() in DAY_NAME_TO_INT:
            day_of_week = DAY_NAME_TO_INT[day_raw.lower()]
        if day_of_week is None:
            errors.append({
                "row": row_idx,
                "error": f"Invalid day of week: '{day_raw}' (must be 0-6 or Monday..Sunday)",
            })
            continue

        # Resolve Slot
        slot_id: Optional[int] = None
        if slot_raw.isdigit():
            s_val = int(slot_raw)
            slot_id = all_slots_by_id.get(s_val) or all_slots.get(s_val)
        if slot_id is None:
            errors.append({"row": row_idx, "error": f"Unknown time slot: '{slot_raw}'"})
            continue

        # Resolve Department
        department_id: Optional[int] = None
        if dept_raw.isdigit():
            department_id = all_depts_by_id.get(int(dept_raw))
        if department_id is None:
            department_id = all_depts.get(dept_raw.upper())
        if department_id is None:
            errors.append({
                "row": row_idx,
                "error": f"Unknown department: '{dept_raw}'",
            })
            continue

        # Check Conflict
        conflict = (
            db.query(TimetableEntry)
            .filter(
                TimetableEntry.room_id == room_id,
                TimetableEntry.day_of_week == day_of_week,
                TimetableEntry.slot_id == slot_id,
            )
            .first()
        )
        if conflict:
            errors.append({
                "row": row_idx,
                "error": f"Slot conflict for room {room_raw} on day {day_raw} slot {slot_raw} (already assigned to '{conflict.subject}')",
            })
            continue

        entry = TimetableEntry(
            room_id=room_id,
            day_of_week=day_of_week,
            slot_id=slot_id,
            department_id=department_id,
            subject=subject,
            faculty_name=faculty,
        )
        db.add(entry)
        db.commit()
        imported += 1

    log_audit(
        db,
        action="TIMETABLE_CSV_IMPORTED",
        entity="TimetableEntry",
        entity_id=None,
        actor_id=actor_id,
        meta={"total": total_rows, "imported": imported, "failed": len(errors)},
    )

    return TimetableImportResponse(
        total_rows=total_rows,
        imported=imported,
        failed=len(errors),
        errors=errors,
    )


# ---------------------------------------------------------
# Booking History & CSV Export Service
# ---------------------------------------------------------

def _build_booking_query(
    db: Session,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    block_id: Optional[int] = None,
    room_id: Optional[int] = None,
    department_id: Optional[int] = None,
    status: Optional[BookingStatus] = None,
    requester: Optional[str] = None,
    requester_type: Optional[RequesterType] = None,
    search: Optional[str] = None,
):
    """Build filtered query for bookings."""
    query = (
        db.query(Booking)
        .join(Booking.room)
        .join(Booking.slot)
        .join(Booking.department)
    )

    if date_from is not None:
        query = query.filter(Booking.date >= date_from)
    if date_to is not None:
        query = query.filter(Booking.date <= date_to)
    if block_id is not None:
        query = query.filter(Room.block_id == block_id)
    if room_id is not None:
        query = query.filter(Booking.room_id == room_id)
    if department_id is not None:
        query = query.filter(Booking.department_id == department_id)
    if status is not None:
        query = query.filter(Booking.status == status)
    if requester_type is not None:
        query = query.filter(Booking.requester_type == requester_type)
    if requester:
        req_term = f"%{requester.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Booking.name).ilike(req_term),
                func.lower(Booking.email).ilike(req_term),
                func.lower(Booking.roll_no).ilike(req_term),
            )
        )
    if search:
        s_term = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Booking.reference).ilike(s_term),
                func.lower(Booking.name).ilike(s_term),
                func.lower(Booking.email).ilike(s_term),
                func.lower(Booking.roll_no).ilike(s_term),
                func.lower(Booking.purpose).ilike(s_term),
            )
        )

    return query


def list_bookings(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    block_id: Optional[int] = None,
    room_id: Optional[int] = None,
    department_id: Optional[int] = None,
    status: Optional[BookingStatus] = None,
    requester: Optional[str] = None,
    requester_type: Optional[RequesterType] = None,
    search: Optional[str] = None,
) -> Tuple[List[Booking], int]:
    """Retrieve bookings list with filters and pagination."""
    query = _build_booking_query(
        db,
        date_from=date_from,
        date_to=date_to,
        block_id=block_id,
        room_id=room_id,
        department_id=department_id,
        status=status,
        requester=requester,
        requester_type=requester_type,
        search=search,
    )

    total = query.count()
    bookings = (
        query.order_by(Booking.date.desc(), Booking.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return bookings, total


def export_bookings_csv(
    db: Session,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    block_id: Optional[int] = None,
    room_id: Optional[int] = None,
    department_id: Optional[int] = None,
    status: Optional[BookingStatus] = None,
    requester: Optional[str] = None,
    requester_type: Optional[RequesterType] = None,
    search: Optional[str] = None,
) -> str:
    """Generate CSV string for filtered bookings."""
    query = _build_booking_query(
        db,
        date_from=date_from,
        date_to=date_to,
        block_id=block_id,
        room_id=room_id,
        department_id=department_id,
        status=status,
        requester=requester,
        requester_type=requester_type,
        search=search,
    )

    bookings = query.order_by(Booking.date.desc(), Booking.id.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Reference",
        "Date",
        "Time Slot",
        "Room",
        "Block",
        "Department",
        "Requester Type",
        "Requester Name",
        "Roll No",
        "Email",
        "Phone",
        "Expected Strength",
        "Status",
        "HOD Approval Required",
        "Purpose",
        "Created At",
    ])

    for b in bookings:
        writer.writerow([
            b.reference,
            b.date.isoformat(),
            b.slot.label if b.slot else str(b.slot_id),
            b.room.name if b.room else str(b.room_id),
            b.room.block.name if b.room and b.room.block else "",
            b.department.code if b.department else str(b.department_id),
            b.requester_type.value,
            b.name,
            b.roll_no or "",
            b.email,
            b.phone,
            b.expected_strength,
            b.status.value,
            "Yes" if b.requires_hod_approval else "No",
            b.purpose,
            b.created_at.isoformat() if b.created_at else "",
        ])

    return output.getvalue()


# ---------------------------------------------------------
# Audit Log Viewer Service
# ---------------------------------------------------------

def list_audit_logs(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    actor_id: Optional[int] = None,
    action: Optional[str] = None,
    entity: Optional[str] = None,
    entity_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    search: Optional[str] = None,
) -> Tuple[List[AuditLog], int]:
    """Retrieve audit logs with filtering and pagination."""
    query = db.query(AuditLog)

    if actor_id is not None:
        query = query.filter(AuditLog.actor_id == actor_id)
    if action is not None:
        query = query.filter(func.lower(AuditLog.action) == action.strip().lower())
    if entity is not None:
        query = query.filter(func.lower(AuditLog.entity) == entity.strip().lower())
    if entity_id is not None:
        query = query.filter(AuditLog.entity_id == str(entity_id))
    if start_date is not None:
        query = query.filter(AuditLog.created_at >= start_date)
    if end_date is not None:
        query = query.filter(AuditLog.created_at <= end_date)
    if search:
        search_term = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(AuditLog.action).ilike(search_term),
                func.lower(AuditLog.entity).ilike(search_term),
                func.lower(AuditLog.entity_id).ilike(search_term),
            )
        )

    total = query.count()
    logs = (
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return logs, total


# ---------------------------------------------------------
# Admin Overview & Room CSV Import Services
# ---------------------------------------------------------

def get_admin_overview(db: Session) -> AdminOverviewResponse:
    """Compute overview statistics, utilization rate, charts data, and activity."""
    today = date.today()
    total_rooms = db.query(Room).count()
    in_maintenance = db.query(Room).filter(Room.status == RoomStatus.MAINTENANCE).count()
    bookings_today = db.query(Booking).filter(Booking.date == today).count()
    pending_bookings = db.query(Booking).filter(Booking.status == BookingStatus.PENDING).count()

    active_rooms = db.query(Room).filter(Room.status == RoomStatus.ACTIVE).count()
    slots_count = db.query(TimeSlot).count() or 6
    daily_capacity_slots = active_rooms * slots_count

    active_today_bookings = (
        db.query(Booking)
        .filter(
            Booking.date == today,
            Booking.status.in_([
                BookingStatus.APPROVED,
                BookingStatus.COORDINATOR_APPROVED,
            ]),
        )
        .count()
    )
    weekday = today.weekday()
    timetable_today_entries = (
        db.query(TimetableEntry)
        .filter(TimetableEntry.day_of_week == weekday)
        .count()
    )
    total_occupied_today = active_today_bookings + timetable_today_entries
    if daily_capacity_slots > 0:
        utilization_rate = round(min(100.0, (total_occupied_today / daily_capacity_slots) * 100), 1)
    else:
        utilization_rate = 0.0

    import datetime as dt_module
    bookings_per_day = []
    for i in range(6, -1, -1):
        target_d = today - dt_module.timedelta(days=i)
        day_bookings = db.query(Booking).filter(Booking.date == target_d).all()
        confirmed = sum(
            1 for b in day_bookings
            if b.status in [BookingStatus.APPROVED, BookingStatus.COORDINATOR_APPROVED]
        )
        pending = sum(1 for b in day_bookings if b.status == BookingStatus.PENDING)
        rejected = sum(
            1 for b in day_bookings
            if b.status in [BookingStatus.REJECTED, BookingStatus.CANCELLED]
        )
        bookings_per_day.append(
            DailyBookingStats(
                date=target_d.isoformat(),
                day=target_d.strftime("%a"),
                total=len(day_bookings),
                confirmed=confirmed,
                pending=pending,
                rejected=rejected,
            )
        )

    room_types = [
        (RoomType.CLASSROOM, "Classrooms"),
        (RoomType.LAB, "Laboratories"),
        (RoomType.EXAM_HALL, "Exam Halls"),
        (RoomType.SEMINAR_HALL, "Seminar Halls"),
    ]
    room_type_usage = []
    for rt, label in room_types:
        r_count = db.query(Room).filter(Room.room_type == rt).count()
        b_count = (
            db.query(Booking)
            .join(Room, Booking.room_id == Room.id)
            .filter(Room.room_type == rt)
            .count()
        )
        room_type_usage.append(
            RoomTypeUsageStats(
                room_type=rt.value,
                label=label,
                room_count=r_count,
                booking_count=b_count,
            )
        )

    recent_logs = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(10)
        .all()
    )
    recent_activity = [
        {
            "id": log.id,
            "action": log.action,
            "entity": log.entity,
            "entity_id": log.entity_id,
            "actor_id": log.actor_id,
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "meta": log.meta or {},
        }
        for log in recent_logs
    ]

    return AdminOverviewResponse(
        total_rooms=total_rooms,
        in_maintenance=in_maintenance,
        bookings_today=bookings_today,
        pending_bookings=pending_bookings,
        utilization_rate=utilization_rate,
        bookings_per_day=bookings_per_day,
        room_type_usage=room_type_usage,
        recent_activity=recent_activity,
    )


def import_rooms_csv(
    db: Session, csv_content: str, actor_id: int
) -> RoomImportResponse:
    """Import rooms in bulk from CSV content with validation."""
    reader = csv.DictReader(io.StringIO(csv_content.strip()))
    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty or missing header line",
        )

    def _get_val(row: Dict[str, str], *aliases: str) -> Optional[str]:
        for alias in aliases:
            for k in row:
                if k and k.strip().lower() == alias.lower():
                    val = row[k]
                    return val.strip() if val else None
        return None

    total_rows = 0
    imported = 0
    errors: List[Dict[str, Any]] = []

    all_blocks = {b.name.lower(): b.id for b in db.query(Block).all()}
    all_blocks_by_id = {b.id: b.id for b in db.query(Block).all()}
    all_depts = {d.code.upper(): d.id for d in db.query(Department).all()}
    all_depts.update({d.name.lower(): d.id for d in db.query(Department).all()})
    all_depts_by_id = {d.id: d.id for d in db.query(Department).all()}
    all_facilities = {f.name.lower(): f for f in db.query(Facility).all()}

    room_type_map = {
        "classroom": RoomType.CLASSROOM,
        "lab": RoomType.LAB,
        "laboratory": RoomType.LAB,
        "exam_hall": RoomType.EXAM_HALL,
        "exam": RoomType.EXAM_HALL,
        "seminar_hall": RoomType.SEMINAR_HALL,
        "seminar": RoomType.SEMINAR_HALL,
    }

    for row_idx, row in enumerate(reader, start=2):
        total_rows += 1
        name = _get_val(row, "name", "room_name", "room", "room_number")
        block_raw = _get_val(row, "block", "block_id", "block_name", "building")
        floor_raw = _get_val(row, "floor", "floor_number")
        type_raw = _get_val(row, "room_type", "type", "category")
        cap_raw = _get_val(row, "capacity", "seats", "size")
        dept_raw = _get_val(row, "department", "department_id", "dept", "dept_code")
        facilities_raw = _get_val(row, "facilities", "amenities", "facility_list")
        status_raw = _get_val(row, "status", "room_status")
        note = _get_val(row, "maintenance_note", "note")

        if not name or not block_raw or not cap_raw:
            errors.append({
                "row": row_idx,
                "error": "Missing required fields (need at least name, block, capacity)",
            })
            continue

        try:
            capacity = int(cap_raw)
            if capacity <= 0:
                raise ValueError()
        except ValueError:
            errors.append({"row": row_idx, "error": f"Invalid capacity '{cap_raw}' (must be positive integer)"})
            continue

        floor = 1
        if floor_raw:
            try:
                floor = int(floor_raw)
            except ValueError:
                floor = 1

        room_type = RoomType.CLASSROOM
        if type_raw:
            rt_key = type_raw.lower().replace(" ", "_").replace("-", "_")
            if rt_key in room_type_map:
                room_type = room_type_map[rt_key]
            else:
                errors.append({"row": row_idx, "error": f"Invalid room type '{type_raw}'"})
                continue

        block_id = None
        if block_raw.isdigit():
            block_id = all_blocks_by_id.get(int(block_raw))
        if block_id is None:
            block_id = all_blocks.get(block_raw.lower())
        if block_id is None:
            errors.append({"row": row_idx, "error": f"Unknown block '{block_raw}'"})
            continue

        dept_id = None
        if dept_raw:
            if dept_raw.isdigit():
                dept_id = all_depts_by_id.get(int(dept_raw))
            if dept_id is None:
                dept_id = all_depts.get(dept_raw.upper()) or all_depts.get(dept_raw.lower())
            if dept_id is None:
                errors.append({"row": row_idx, "error": f"Unknown department '{dept_raw}'"})
                continue

        if room_type == RoomType.LAB and not dept_id:
            errors.append({"row": row_idx, "error": "Department is required for LAB rooms"})
            continue

        room_status = RoomStatus.ACTIVE
        if status_raw and status_raw.upper() in ["MAINTENANCE", "INACTIVE", "OFFLINE"]:
            room_status = RoomStatus.MAINTENANCE

        matched_facilities = []
        if facilities_raw:
            fac_items = [f.strip() for f in facilities_raw.replace(";", ",").split(",") if f.strip()]
            for item in fac_items:
                f_obj = all_facilities.get(item.lower())
                if not f_obj:
                    f_obj = Facility(name=item)
                    db.add(f_obj)
                    db.flush()
                    all_facilities[item.lower()] = f_obj
                matched_facilities.append(f_obj)

        existing = db.query(Room).filter(func.lower(Room.name) == name.strip().lower()).first()
        if existing:
            existing.block_id = block_id
            existing.floor = floor
            existing.room_type = room_type
            existing.capacity = capacity
            existing.department_id = dept_id
            existing.status = room_status
            if note:
                existing.maintenance_note = note
            if matched_facilities:
                existing.facilities = matched_facilities
        else:
            new_room = Room(
                name=name.strip(),
                block_id=block_id,
                floor=floor,
                room_type=room_type,
                capacity=capacity,
                department_id=dept_id,
                status=room_status,
                maintenance_note=note,
                facilities=matched_facilities,
            )
            db.add(new_room)

        imported += 1

    db.commit()

    log_audit(
        db,
        action="ROOMS_CSV_IMPORTED",
        entity="Room",
        entity_id="bulk",
        actor_id=actor_id,
        meta={"total_rows": total_rows, "imported": imported, "error_count": len(errors)},
    )

    return RoomImportResponse(
        total_rows=total_rows,
        imported=imported,
        errors=errors,
    )


