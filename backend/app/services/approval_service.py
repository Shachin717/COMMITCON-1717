from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.approval_policy import ApprovalPolicy
from app.models.booking import Booking
from app.models.booking_approval import BookingApproval
from app.models.classroom import Classroom
from app.models.department import Department
from app.models.user import User
from app.schemas.approval import ApprovalPolicyUpdate, ApprovalDecision, HODBookingDetail
from app.core.exceptions import ResourceNotFoundException, ValidationBusinessException, ForbiddenException
from app.repositories.booking_repository import BookingRepository

class ApprovalService:
    def __init__(self, db: Session):
        self.db = db
        self.booking_repo = BookingRepository(db)

    def list_policies(self) -> List[ApprovalPolicy]:
        return self.db.query(ApprovalPolicy).all()

    def update_policy(self, policy_id: int, payload: ApprovalPolicyUpdate) -> ApprovalPolicy:
        policy = self.db.query(ApprovalPolicy).filter(ApprovalPolicy.id == policy_id).first()
        if not policy:
            raise ResourceNotFoundException("ApprovalPolicy", policy_id)
            
        if payload.requires_hod_approval is not None:
            policy.requires_hod_approval = payload.requires_hod_approval
        if payload.is_active is not None:
            policy.is_active = payload.is_active
            
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def check_requires_approval(self, purpose: str) -> bool:
        policy = self.db.query(ApprovalPolicy).filter(
            ApprovalPolicy.purpose == purpose,
            ApprovalPolicy.is_active == True
        ).first()
        if policy:
            return policy.requires_hod_approval
        return False

    def get_pending_requests(self, hod_department_id: int, status_filter: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[dict]:
        query = self.db.query(Booking, Classroom.name.label("room_name"), Department.name.label("department_name"), User.username.label("requester_username")).join(
            Classroom, Booking.room_id == Classroom.id
        ).outerjoin(
            Department, Booking.department_id == Department.id
        ).outerjoin(
            User, Booking.requested_by_user_id == User.id
        ).filter(
            Booking.department_id == hod_department_id
        )
        
        if status_filter:
            query = query.filter(Booking.status == status_filter)
        else:
            query = query.filter(Booking.status == "PENDING_HOD_APPROVAL")
            
        results = query.offset(skip).limit(limit).all()
        
        response = []
        for row in results:
            booking, room_name, department_name, requester_username = row
            booking_dict = {
                "id": booking.id,
                "room_id": booking.room_id,
                "title": booking.title,
                "purpose": booking.purpose,
                "department_id": booking.department_id,
                "start_datetime": booking.start_datetime,
                "end_datetime": booking.end_datetime,
                "status": booking.status,
                "requested_by_user_id": booking.requested_by_user_id,
                "rejection_reason": booking.rejection_reason,
                "created_at": booking.created_at,
                "updated_at": booking.updated_at,
                "room_name": room_name,
                "department_name": department_name,
                "requester_username": requester_username,
                "approvals": []
            }
            response.append(booking_dict)
            
        return response

    def approve_or_reject(self, booking_id: int, hod_user_id: int, hod_department_id: int, decision_data: ApprovalDecision) -> Booking:
        booking = self.db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise ResourceNotFoundException("Booking", booking_id)
            
        if booking.status != "PENDING_HOD_APPROVAL":
            raise ValidationBusinessException(detail="Booking is not pending HOD approval")
            
        if booking.department_id != hod_department_id:
            raise ForbiddenException(detail="Cannot approve bookings for other departments")

        if decision_data.decision == "APPROVED":
            conflicts = self.booking_repo.check_conflicts(
                room_id=booking.room_id,
                start_dt=booking.start_datetime,
                end_dt=booking.end_datetime,
                exclude_booking_id=booking.id
            )
            has_conflicts = bool(conflicts["bookings"] or conflicts["allocations"] or conflicts["maintenance"])
            if has_conflicts:
                raise ValidationBusinessException(detail="Room is no longer available for this time slot")
            booking.status = "CONFIRMED"
        else:
            booking.status = "REJECTED"
            booking.rejection_reason = decision_data.remarks

        approval = BookingApproval(
            booking_id=booking.id,
            approver_user_id=hod_user_id,
            decision=decision_data.decision,
            remarks=decision_data.remarks
        )
        self.db.add(approval)
        self.db.commit()
        self.db.refresh(booking)
        
        return booking

    def get_hod_history(self, hod_user_id: int, skip: int = 0, limit: int = 100) -> List[BookingApproval]:
        return self.db.query(BookingApproval).filter(
            BookingApproval.approver_user_id == hod_user_id
        ).order_by(BookingApproval.decided_at.desc()).offset(skip).limit(limit).all()
