from typing import List, Dict, Any
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.core.security import require_admin, require_hod
from app.schemas.user import HODCreate, HODUpdate, UserResponse
from app.schemas.approval import ApprovalPolicyResponse, ApprovalPolicyUpdate, ApprovalDecision, BookingApprovalResponse, HODBookingDetail
from app.services.hod_service import HODService
from app.services.approval_service import ApprovalService
from app.models.booking import Booking

router = APIRouter(tags=["HOD"])

# Admin HOD management
@router.post("/hod/accounts", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_hod_account(payload: HODCreate, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    service = HODService(db)
    return service.create_hod(payload)

@router.get("/hod/accounts", response_model=List[UserResponse])
def list_hod_accounts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    service = HODService(db)
    return service.list_hods(skip=skip, limit=limit)

@router.get("/hod/accounts/{hod_id}", response_model=UserResponse)
def get_hod_account(hod_id: int, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    service = HODService(db)
    return service.get_hod(hod_id)

@router.patch("/hod/accounts/{hod_id}", response_model=UserResponse)
def update_hod_account(hod_id: int, payload: HODUpdate, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    service = HODService(db)
    return service.update_hod(hod_id, payload)

@router.post("/hod/accounts/{hod_id}/deactivate", response_model=UserResponse)
def deactivate_hod(hod_id: int, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    service = HODService(db)
    return service.deactivate_hod(hod_id)

@router.post("/hod/accounts/{hod_id}/reset-password", response_model=UserResponse)
def reset_hod_password(hod_id: int, new_password: str, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    service = HODService(db)
    return service.reset_hod_password(hod_id, new_password)

# Approval policies
@router.get("/approval-policies", response_model=List[ApprovalPolicyResponse])
def list_approval_policies(db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    service = ApprovalService(db)
    return service.list_policies()

@router.patch("/approval-policies/{id}", response_model=ApprovalPolicyResponse)
def update_approval_policy(id: int, payload: ApprovalPolicyUpdate, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    service = ApprovalService(db)
    return service.update_policy(id, payload)

# HOD portal endpoints
@router.get("/hod/requests", response_model=List[HODBookingDetail])
def get_hod_requests(status: str = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: dict = Depends(require_hod)):
    service = ApprovalService(db)
    # The JWT token in dev might not have department_id, but the actual user does. So get the user's dept id.
    from app.services.hod_service import HODService
    hod_service = HODService(db)
    user = hod_service.get_hod(current_user["user_id"])
    return service.get_pending_requests(user.department_id, status_filter=status, skip=skip, limit=limit)

@router.get("/hod/requests/{booking_id}", response_model=HODBookingDetail)
def get_hod_request(booking_id: int, db: Session = Depends(get_db), current_user: dict = Depends(require_hod)):
    service = ApprovalService(db)
    from app.services.hod_service import HODService
    hod_service = HODService(db)
    user = hod_service.get_hod(current_user["user_id"])
    
    # Simple list filter for now to get detail
    requests = service.get_pending_requests(user.department_id, skip=0, limit=1000)
    for req in requests:
        if req["id"] == booking_id:
            return req
    from app.core.exceptions import ResourceNotFoundException
    raise ResourceNotFoundException("Request", booking_id)

@router.post("/hod/requests/{booking_id}/decide", response_model=BookingApprovalResponse)
def decide_request(booking_id: int, payload: ApprovalDecision, db: Session = Depends(get_db), current_user: dict = Depends(require_hod)):
    service = ApprovalService(db)
    from app.services.hod_service import HODService
    hod_service = HODService(db)
    user = hod_service.get_hod(current_user["user_id"])
    
    booking = service.approve_or_reject(
        booking_id=booking_id,
        hod_user_id=user.id,
        hod_department_id=user.department_id,
        decision_data=payload
    )
    
    # We need to return BookingApprovalResponse, which matches the latest approval
    # Getting the latest approval for this booking
    from app.models.booking_approval import BookingApproval
    approval = db.query(BookingApproval).filter(BookingApproval.booking_id == booking_id).order_by(BookingApproval.decided_at.desc()).first()
    return approval

@router.get("/hod/history", response_model=List[BookingApprovalResponse])
def hod_history(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: dict = Depends(require_hod)):
    service = ApprovalService(db)
    from app.services.hod_service import HODService
    hod_service = HODService(db)
    user = hod_service.get_hod(current_user["user_id"])
    return service.get_hod_history(user.id, skip=skip, limit=limit)

@router.get("/hod/dashboard")
def hod_dashboard(db: Session = Depends(get_db), current_user: dict = Depends(require_hod)):
    service = ApprovalService(db)
    from app.services.hod_service import HODService
    hod_service = HODService(db)
    user = hod_service.get_hod(current_user["user_id"])
    
    from app.models.department import Department
    dept = db.query(Department).filter(Department.id == user.department_id).first()
    
    pending_count = db.query(Booking).filter(Booking.department_id == user.department_id, Booking.status == "PENDING_HOD_APPROVAL").count()
    approved_count = db.query(Booking).filter(Booking.department_id == user.department_id, Booking.status == "CONFIRMED").count() # Approximation
    rejected_count = db.query(Booking).filter(Booking.department_id == user.department_id, Booking.status == "REJECTED").count()
    total = pending_count + approved_count + rejected_count
    
    recent = service.get_pending_requests(user.department_id, skip=0, limit=5)
    
    return {
        "pending_count": pending_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "total_count": total,
        "department_name": dept.name if dept else "Unknown",
        "recent_requests": recent
    }
