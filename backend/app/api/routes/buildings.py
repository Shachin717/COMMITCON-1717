from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.building import BuildingCreate, BuildingUpdate, BuildingResponse
from app.services.department_service import DepartmentService
from app.core.security import require_admin

router = APIRouter(prefix="/buildings", tags=["Buildings"])


@router.post("", response_model=BuildingResponse, status_code=status.HTTP_201_CREATED)
def create_building(
    payload: BuildingCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = DepartmentService(db)
    return service.create_building(payload)


@router.get("", response_model=List[BuildingResponse])
def list_buildings(db: Session = Depends(get_db)):
    service = DepartmentService(db)
    return service.list_buildings()


@router.patch("/{building_id}", response_model=BuildingResponse)
def update_building(
    building_id: int,
    payload: BuildingUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = DepartmentService(db)
    return service.update_building(building_id, payload)


@router.delete("/{building_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_building(
    building_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = DepartmentService(db)
    service.delete_building(building_id)

