import threading
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.booking import Booking
from app.models.classroom import Classroom
from app.models.room_unavailability import RoomUnavailability
from app.schemas.booking import (
    BookingCreate,
    BookingUpdate,
    BookingResponse,
    RoomUnavailabilityCreate,
    RoomUnavailabilityResponse,
    UnavailabilityConflictCheckResponse,
)
from app.repositories.booking_repository import BookingRepository
from app.repositories.classroom_repository import ClassroomRepository
from app.core.exceptions import (
    ResourceNotFoundException,
    ConflictException,
    ValidationBusinessException,
)

# Mutex registry for room-level concurrency control
_room_locks: Dict[int, threading.Lock] = {}
_room_locks_mutex = threading.Lock()


from app.services.approval_service import ApprovalService

def get_room_lock(room_id: int) -> threading.Lock:
    with _room_locks_mutex:
        if room_id not in _room_locks:
            _room_locks[room_id] = threading.Lock()
        return _room_locks[room_id]


class BookingService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = BookingRepository(db)
        self.classroom_repo = ClassroomRepository(db)
        self.approval_service = ApprovalService(db)

    def get_booking(self, booking_id: int) -> BookingResponse:
        b = self.repo.get_by_id(booking_id)
        if not b:
            raise ResourceNotFoundException("Booking", booking_id)
        return BookingResponse.model_validate(b)

    def list_bookings(
        self,
        room_id: Optional[int] = None,
        status: Optional[str] = None,
        department_id: Optional[int] = None,
        purpose: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[BookingResponse]:
        bookings = self.repo.get_all(room_id=room_id, status=status, skip=skip, limit=limit)
        if department_id:
            bookings = [b for b in bookings if b.department_id == department_id]
        if purpose:
            bookings = [b for b in bookings if b.purpose == purpose]
        return [BookingResponse.model_validate(b) for b in bookings]

    def create_booking(self, obj_in: BookingCreate, user_id: Optional[int] = None) -> BookingResponse:
        # Enforce room-level lock for concurrency safety across threads and processes
        room_lock = get_room_lock(obj_in.room_id)
        with room_lock:
            # 1. Lock room in DB and verify room exists and active
            room = self.repo.lock_room(obj_in.room_id)
            if not room:
                raise ResourceNotFoundException("Classroom", obj_in.room_id)
            if not room.is_active:
                raise ValidationBusinessException(f"Room '{room.name}' is currently inactive.")

            # 2. Lab department access check if lab
            if room.room_type == "LAB" and obj_in.department_id:
                auth_dept_ids = {da.department_id for da in room.department_accesses}
                if obj_in.department_id not in auth_dept_ids:
                    raise ValidationBusinessException(
                        f"Department {obj_in.department_id} is not authorized to book LAB '{room.name}'."
                    )

            # 3. Check for overlapping conflicts inside the locked critical section
            conflicts = self.repo.check_conflicts(
                room_id=obj_in.room_id,
                start_dt=obj_in.start_datetime,
                end_dt=obj_in.end_datetime,
            )
            has_conflicts = (
                len(conflicts["bookings"]) > 0
                or len(conflicts["maintenance"]) > 0
                or len(conflicts["allocations"]) > 0
            )
            if has_conflicts:
                conflict_details = []
                if conflicts["bookings"]:
                    conflict_details.append(f"{len(conflicts['bookings'])} existing booking(s)")
                if conflicts["maintenance"]:
                    conflict_details.append(f"{len(conflicts['maintenance'])} maintenance interval(s)")
                if conflicts["allocations"]:
                    conflict_details.append(f"{len(conflicts['allocations'])} published class allocation(s)")
                raise ConflictException(
                    f"Booking conflict detected for room '{room.name}': Overlaps with {', '.join(conflict_details)}."
                )

            # 4. Check approval policy
            requires_approval = False
            if obj_in.purpose:
                requires_approval = self.approval_service.check_requires_approval(obj_in.purpose)
            
            if requires_approval:
                obj_in.status = "PENDING_HOD_APPROVAL"
            elif obj_in.status == "PENDING_HOD_APPROVAL":
                # If they explicitly requested pending but it doesn't need it, reset to confirmed (or keep whatever logic)
                obj_in.status = "CONFIRMED"

            booking = self.repo.create(obj_in, requested_by_user_id=user_id)
            return BookingResponse.model_validate(booking)

    def update_booking(self, booking_id: int, obj_in: BookingUpdate) -> BookingResponse:
        booking = self.repo.get_by_id(booking_id)
        if not booking:
            raise ResourceNotFoundException("Booking", booking_id)

        if booking.status == "CANCELLED":
            raise ValidationBusinessException("Cannot edit a cancelled booking.")

        target_room_id = booking.room_id
        target_start = obj_in.start_datetime or booking.start_datetime
        target_end = obj_in.end_datetime or booking.end_datetime

        room_lock = get_room_lock(target_room_id)
        with room_lock:
            if obj_in.start_datetime or obj_in.end_datetime:
                conflicts = self.repo.check_conflicts(
                    room_id=target_room_id,
                    start_dt=target_start,
                    end_dt=target_end,
                    exclude_booking_id=booking_id,
                )
                if conflicts["bookings"] or conflicts["maintenance"] or conflicts["allocations"]:
                    raise ConflictException("Requested time update conflicts with existing commitments.")

            updated = self.repo.update(booking, obj_in)
            return BookingResponse.model_validate(updated)

    def cancel_booking(self, booking_id: int) -> BookingResponse:
        booking = self.repo.get_by_id(booking_id)
        if not booking:
            raise ResourceNotFoundException("Booking", booking_id)
        if booking.status == "CANCELLED":
            return BookingResponse.model_validate(booking)

        cancelled = self.repo.cancel(booking_id)
        return BookingResponse.model_validate(cancelled)

    # --- Room Unavailability ---
    def check_unavailability_conflicts(
        self, room_id: int, start_dt: Any, end_dt: Any
    ) -> UnavailabilityConflictCheckResponse:
        conflicts = self.repo.check_conflicts(room_id, start_dt, end_dt)
        has_conflicts = bool(conflicts["bookings"] or conflicts["allocations"])
        msg = "No conflicts detected." if not has_conflicts else "Conflicting commitments detected."
        return UnavailabilityConflictCheckResponse(
            has_conflicts=has_conflicts,
            conflicting_bookings=[{"id": b.id, "title": b.title} for b in conflicts["bookings"]],
            conflicting_allocations=[
                {"id": a.id, "class_session_id": a.class_session_id} for a in conflicts["allocations"]
            ],
            message=msg,
        )

    def create_room_unavailability(
        self, obj_in: RoomUnavailabilityCreate
    ) -> RoomUnavailabilityResponse:
        room = self.classroom_repo.get_by_id(obj_in.room_id)
        if not room:
            raise ResourceNotFoundException("Classroom", obj_in.room_id)

        conflicts = self.repo.check_conflicts(
            room_id=obj_in.room_id,
            start_dt=obj_in.start_datetime,
            end_dt=obj_in.end_datetime,
        )
        if (conflicts["bookings"] or conflicts["allocations"]) and not obj_in.force:
            b_count = len(conflicts["bookings"])
            a_count = len(conflicts["allocations"])
            raise ConflictException(
                f"Proposed maintenance period conflicts with {b_count} confirmed booking(s) and "
                f"{a_count} published allocation(s). Set 'force=true' after authorized resolution.",
                errors={
                    "conflicting_booking_ids": [b.id for b in conflicts["bookings"]],
                    "conflicting_allocation_ids": [a.id for a in conflicts["allocations"]],
                },
            )

        unav = self.repo.create_unavailability(obj_in)
        return RoomUnavailabilityResponse.model_validate(unav)

    def list_room_unavailabilities(
        self, room_id: Optional[int] = None, skip: int = 0, limit: int = 100
    ) -> List[RoomUnavailabilityResponse]:
        unavs = self.repo.get_unavailabilities(room_id=room_id, skip=skip, limit=limit)
        return [RoomUnavailabilityResponse.model_validate(u) for u in unavs]

    def delete_room_unavailability(self, unavailability_id: int) -> None:
        deleted = self.repo.delete_unavailability(unavailability_id)
        if not deleted:
            raise ResourceNotFoundException("RoomUnavailability", unavailability_id)

