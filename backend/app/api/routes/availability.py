from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.availability import AvailabilityQuery, AvailabilityResponse
from app.services.availability_service import AvailabilityService

router = APIRouter(tags=["Availability"])


@router.get("/availability", response_model=AvailabilityResponse)
def check_room_availability(
    start_datetime: datetime = Query(..., description="Start of interval in ISO format (e.g. 2026-10-15T09:00:00)"),
    end_datetime: datetime = Query(..., description="End of interval in ISO format (e.g. 2026-10-15T11:00:00)"),
    student_count: Optional[int] = Query(None, ge=0),
    room_type: Optional[str] = Query(None, description="CLASSROOM or LAB"),
    department_id: Optional[int] = Query(None, description="Department requesting access"),
    facility_ids: Optional[List[int]] = Query(None, description="List of required facility IDs"),
    db: Session = Depends(get_db),
):
    query = AvailabilityQuery(
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        student_count=student_count,
        room_type=room_type,
        department_id=department_id,
        required_facility_ids=facility_ids or [],
    )
    service = AvailabilityService(db)
    return service.check_availability(query)

