from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.facility import FacilityCreate, FacilityResponse
from app.schemas.classroom import ClassroomFacilityAdd, ClassroomResponse
from app.services.department_service import DepartmentService
from app.services.classroom_service import ClassroomService
from app.core.security import require_admin

router = APIRouter(tags=["Facilities"])


@router.post("/facilities", response_model=FacilityResponse, status_code=status.HTTP_201_CREATED)
def create_facility(
    payload: FacilityCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = DepartmentService(db)
    return service.create_facility(payload)


@router.get("/facilities", response_model=List[FacilityResponse])
def list_facilities(db: Session = Depends(get_db)):
    service = DepartmentService(db)
    return service.list_facilities()


@router.post("/classrooms/{room_id}/facilities", response_model=ClassroomResponse)
def add_facility_to_room(
    room_id: int,
    payload: ClassroomFacilityAdd,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = ClassroomService(db)
    return service.add_facility_to_room(room_id, payload.facility_id)


@router.delete("/classrooms/{room_id}/facilities/{facility_id}", response_model=ClassroomResponse)
def remove_facility_from_room(
    room_id: int,
    facility_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = ClassroomService(db)
    return service.remove_facility_from_room(room_id, facility_id)

