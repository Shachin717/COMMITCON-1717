from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.booking import (
    BookingCreate,
    BookingUpdate,
    BookingResponse,
    RoomUnavailabilityCreate,
    RoomUnavailabilityResponse,
    UnavailabilityConflictCheckResponse,
)
from app.services.booking_service import BookingService
from app.core.security import require_admin, get_current_user

router = APIRouter(tags=["Bookings & Unavailability"])


# --- Bookings ---
@router.post("/bookings", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = BookingService(db)
    user_id = current_user.get("user_id")
    return service.create_booking(payload, user_id=user_id)


@router.get("/bookings", response_model=List[BookingResponse])
def list_bookings(
    room_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    purpose: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    service = BookingService(db)
    return service.list_bookings(
        room_id=room_id, status=status, department_id=department_id, purpose=purpose, skip=skip, limit=limit
    )


@router.get("/bookings/{booking_id}", response_model=BookingResponse)
def get_booking(booking_id: int, db: Session = Depends(get_db)):
    service = BookingService(db)
    return service.get_booking(booking_id)


@router.patch("/bookings/{booking_id}", response_model=BookingResponse)
def update_booking(
    booking_id: int,
    payload: BookingUpdate,
    db: Session = Depends(get_db),
):
    service = BookingService(db)
    return service.update_booking(booking_id, payload)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingResponse)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
):
    service = BookingService(db)
    return service.cancel_booking(booking_id)


# --- Room Unavailability ---
@router.post("/room-unavailability", response_model=RoomUnavailabilityResponse, status_code=status.HTTP_201_CREATED)
def create_room_unavailability(
    payload: RoomUnavailabilityCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = BookingService(db)
    return service.create_room_unavailability(payload)


@router.get("/room-unavailability/check-conflicts", response_model=UnavailabilityConflictCheckResponse)
def check_unavailability_conflicts(
    room_id: int = Query(...),
    start_datetime: datetime = Query(...),
    end_datetime: datetime = Query(...),
    db: Session = Depends(get_db),
):
    service = BookingService(db)
    return service.check_unavailability_conflicts(room_id, start_datetime, end_datetime)


@router.get("/room-unavailability", response_model=List[RoomUnavailabilityResponse])
def list_room_unavailabilities(
    room_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    service = BookingService(db)
    return service.list_room_unavailabilities(room_id=room_id, skip=skip, limit=limit)


@router.delete("/room-unavailability/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room_unavailability(
    id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    service = BookingService(db)
    service.delete_room_unavailability(id)

