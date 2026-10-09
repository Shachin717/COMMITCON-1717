from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.class_group import ClassGroupCreate, ClassGroupUpdate, ClassGroupResponse
from app.schemas.class_session import (
    ClassSessionCreate,
    ClassSessionUpdate,
    ClassSessionResponse,
    TimeSlotCreate,
    TimeSlotResponse,
)
from app.services.schedule_service import ScheduleService
from app.core.security import require_admin

router = APIRouter(tags=["Class Groups & Schedules"])


# --- Class Groups ---
@router.post("/class-groups", response_model=ClassGroupResponse, status_code=status.HTTP_201_CREATED)
def create_class_group(
    payload: ClassGroupCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = ScheduleService(db)
    return service.create_group(payload)


@router.get("/class-groups", response_model=List[ClassGroupResponse])
def list_class_groups(
    department_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    service = ScheduleService(db)
    return service.list_groups(department_id=department_id, is_active=is_active, skip=skip, limit=limit)


@router.patch("/class-groups/{class_id}", response_model=ClassGroupResponse)
def update_class_group(
    class_id: int,
    payload: ClassGroupUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = ScheduleService(db)
    return service.update_group(class_id, payload)


# --- Class Sessions ---
@router.post("/class-sessions", response_model=ClassSessionResponse, status_code=status.HTTP_201_CREATED)
def create_class_session(
    payload: ClassSessionCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = ScheduleService(db)
    return service.create_session(payload)


@router.get("/class-sessions", response_model=List[ClassSessionResponse])
def list_class_sessions(
    class_group_id: Optional[int] = Query(None),
    session_date: Optional[date] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    service = ScheduleService(db)
    return service.list_sessions(
        class_group_id=class_group_id,
        session_date=session_date,
        status=status,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )


@router.get("/class-sessions/{session_id}", response_model=ClassSessionResponse)
def get_class_session(session_id: int, db: Session = Depends(get_db)):
    service = ScheduleService(db)
    return service.get_session(session_id)


@router.patch("/class-sessions/{session_id}", response_model=ClassSessionResponse)
def update_class_session(
    session_id: int,
    payload: ClassSessionUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = ScheduleService(db)
    return service.update_session(session_id, payload)


@router.delete("/class-sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class_session(
    session_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = ScheduleService(db)
    service.delete_session(session_id)


# --- Time Slots ---
@router.get("/time-slots", response_model=List[TimeSlotResponse])
def list_time_slots(db: Session = Depends(get_db)):
    service = ScheduleService(db)
    return service.list_time_slots()


@router.post("/time-slots", response_model=TimeSlotResponse, status_code=status.HTTP_201_CREATED)
def create_time_slot(
    payload: TimeSlotCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = ScheduleService(db)
    return service.create_time_slot(payload)

