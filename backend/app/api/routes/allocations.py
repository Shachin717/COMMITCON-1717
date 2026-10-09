from typing import List, Any, Dict
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.allocation import (
    AllocationGenerateRequest,
    AllocationRunResponse,
    ReallocationSummary,
)
from app.schemas.metrics import BenchmarkComparisonResponse
from app.services.allocation_service import AllocationService
from app.core.security import require_admin

router = APIRouter(prefix="/allocations", tags=["Allocations & Optimization"])


@router.post("/generate", response_model=AllocationRunResponse, status_code=status.HTTP_201_CREATED)
def generate_allocations(
    payload: AllocationGenerateRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = AllocationService(db)
    return service.generate_allocation(payload)


@router.get("", response_model=List[AllocationRunResponse])
def list_allocation_runs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = AllocationService(db)
    return service.list_allocation_runs(skip=skip, limit=limit)


@router.get("/{allocation_run_id}", response_model=AllocationRunResponse)
def get_allocation_run(
    allocation_run_id: int,
    db: Session = Depends(get_db),
):
    service = AllocationService(db)
    return service.get_allocation_run(allocation_run_id)


@router.get("/{allocation_run_id}/metrics")
def get_allocation_run_metrics(
    allocation_run_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    service = AllocationService(db)
    run = service.alloc_repo.get_run_by_id(allocation_run_id)
    if not run:
        from app.core.exceptions import ResourceNotFoundException
        raise ResourceNotFoundException("AllocationRun", allocation_run_id)
    return run.metrics or {}


@router.post("/{allocation_run_id}/publish", response_model=AllocationRunResponse)
def publish_allocation(
    allocation_run_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = AllocationService(db)
    return service.publish_allocation(allocation_run_id)


@router.post("/{allocation_run_id}/reoptimize", response_model=ReallocationSummary)
def reoptimize_allocation(
    allocation_run_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = AllocationService(db)
    return service.reoptimize(allocation_run_id)

