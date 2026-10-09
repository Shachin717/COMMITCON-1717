from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.classroom import Classroom
from app.repositories.classroom_repository import ClassroomRepository
from app.repositories.booking_repository import BookingRepository
from app.services.classroom_service import ClassroomService
from app.schemas.availability import (
    AvailabilityQuery,
    AvailabilityResponse,
    AvailableRoomItem,
)
from app.schemas.classroom import ClassroomResponse


class AvailabilityService:
    def __init__(self, db: Session):
        self.db = db
        self.classroom_repo = ClassroomRepository(db)
        self.booking_repo = BookingRepository(db)
        self.classroom_service = ClassroomService(db)

    def evaluate_room_eligibility(
        self,
        room: Classroom,
        start_dt: datetime,
        end_dt: datetime,
        student_count: Optional[int] = None,
        room_type: Optional[str] = None,
        department_id: Optional[int] = None,
        required_facility_ids: Optional[List[int]] = None,
    ) -> AvailableRoomItem:
        reasons = []

        # 1. Active check
        if not room.is_active:
            reasons.append("Room is currently inactive.")

        # 2. Capacity check
        if student_count is not None and room.capacity < student_count:
            reasons.append(
                f"Insufficient capacity: Room has {room.capacity} seats, needed {student_count}."
            )

        # 3. Room type check
        if room_type is not None and room.room_type != room_type:
            reasons.append(
                f"Room type mismatch: Room is {room.room_type}, requested {room_type}."
            )

        # 4. Facilities check
        if required_facility_ids:
            room_fac_ids = {cf.facility_id for cf in room.facilities}
            missing_facs = set(required_facility_ids) - room_fac_ids
            if missing_facs:
                reasons.append(
                    f"Missing required facility IDs: {list(missing_facs)}."
                )

        # 5. Lab department access check
        if room.room_type == "LAB":
            authorized_depts = {da.department_id for da in room.department_accesses}
            if not authorized_depts:
                reasons.append("Lab has no authorized departments configured.")
            elif department_id is not None and department_id not in authorized_depts:
                reasons.append(
                    f"Department {department_id} does not have access permission to this lab."
                )

        # 6. Availability interval check (maintenance, bookings, published allocations)
        conflicts = self.booking_repo.check_conflicts(room.id, start_dt, end_dt)
        if conflicts["maintenance"]:
            reasons.append(
                f"Room is blocked for maintenance during this interval ({len(conflicts['maintenance'])} periods)."
            )
        if conflicts["bookings"]:
            reasons.append(
                f"Room has {len(conflicts['bookings'])} conflicting confirmed bookings."
            )
        if conflicts["allocations"]:
            reasons.append(
                f"Room has {len(conflicts['allocations'])} conflicting published class allocations."
            )

        is_eligible = len(reasons) == 0
        excess_cap = (room.capacity - student_count) if (student_count is not None and is_eligible) else None

        room_resp = self.classroom_service._to_response(room)
        return AvailableRoomItem(
            classroom=room_resp,
            is_eligible=is_eligible,
            ineligibility_reasons=reasons,
            excess_capacity=excess_cap,
        )

    def check_availability(self, query: AvailabilityQuery) -> AvailabilityResponse:
        all_rooms = self.classroom_repo.get_all(is_active=True, limit=1000)

        evaluations = []
        eligible_rooms = []

        for room in all_rooms:
            eval_item = self.evaluate_room_eligibility(
                room=room,
                start_dt=query.start_datetime,
                end_dt=query.end_datetime,
                student_count=query.student_count,
                room_type=query.room_type,
                department_id=query.department_id,
                required_facility_ids=query.required_facility_ids,
            )
            evaluations.append(eval_item)
            if eval_item.is_eligible:
                eligible_rooms.append(eval_item.classroom)

        # Sort eligible rooms by capacity ascending (tightest fit first)
        eligible_rooms.sort(key=lambda r: r.capacity)

        return AvailabilityResponse(
            query=query,
            total_eligible=len(eligible_rooms),
            eligible_rooms=eligible_rooms,
            evaluations=evaluations,
        )

