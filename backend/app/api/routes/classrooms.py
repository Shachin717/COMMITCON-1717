from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.classroom import (
    ClassroomCreate,
    ClassroomUpdate,
    ClassroomResponse,
    LabAccessUpdate,
)
from app.services.classroom_service import ClassroomService
from app.core.security import require_admin

router = APIRouter(prefix="/classrooms", tags=["Classrooms & Labs"])


@router.post("", response_model=ClassroomResponse, status_code=status.HTTP_201_CREATED)
def create_classroom(
    payload: ClassroomCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = ClassroomService(db)
    return service.create_classroom(payload)


@router.get("", response_model=List[ClassroomResponse])
def list_classrooms(
    room_type: Optional[str] = Query(None, description="CLASSROOM or LAB"),
    min_capacity: Optional[int] = Query(None, ge=1),
    building_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(None),
    facility_ids: Optional[List[int]] = Query(None, description="Filter rooms having all specified facilities"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    service = ClassroomService(db)
    return service.list_classrooms(
        room_type=room_type,
        min_capacity=min_capacity,
        building_id=building_id,
        is_active=is_active,
        facility_ids=facility_ids,
        skip=skip,
        limit=limit,
    )


@router.get("/{room_id}", response_model=ClassroomResponse)
def get_classroom(room_id: int, db: Session = Depends(get_db)):
    service = ClassroomService(db)
    return service.get_classroom(room_id)


@router.patch("/{room_id}", response_model=ClassroomResponse)
def update_classroom(
    room_id: int,
    payload: ClassroomUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = ClassroomService(db)
    return service.update_classroom(room_id, payload)


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_classroom(
    room_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = ClassroomService(db)
    service.delete_classroom(room_id)


@router.put("/{room_id}/department-access", response_model=List[int])
def set_lab_department_access(
    room_id: int,
    payload: LabAccessUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = ClassroomService(db)
    return service.set_lab_department_access(room_id, payload.department_ids)


@router.get("/{room_id}/department-access", response_model=List[int])
def get_lab_department_access(
    room_id: int,
    db: Session = Depends(get_db),
):
    service = ClassroomService(db)
    return service.get_lab_department_access(room_id)

