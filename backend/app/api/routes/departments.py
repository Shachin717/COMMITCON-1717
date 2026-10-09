from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.department import DepartmentCreate, DepartmentUpdate, DepartmentResponse
from app.services.department_service import DepartmentService
from app.core.security import require_admin

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = DepartmentService(db)
    return service.create_department(payload)


@router.get("", response_model=List[DepartmentResponse])
def list_departments(db: Session = Depends(get_db)):
    service = DepartmentService(db)
    return service.list_departments()


@router.get("/{department_id}", response_model=DepartmentResponse)
def get_department(department_id: int, db: Session = Depends(get_db)):
    service = DepartmentService(db)
    return service.get_department(department_id)


@router.patch("/{department_id}", response_model=DepartmentResponse)
def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = DepartmentService(db)
    return service.update_department(department_id, payload)


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = DepartmentService(db)
    service.delete_department(department_id)

