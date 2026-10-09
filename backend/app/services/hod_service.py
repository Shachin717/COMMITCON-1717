from typing import List
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.department import Department
from app.schemas.user import HODCreate, HODUpdate, UserResponse
from app.core.exceptions import ResourceNotFoundException, ValidationBusinessException
from app.core.security import get_password_hash

class HODService:
    def __init__(self, db: Session):
        self.db = db

    def create_hod(self, payload: HODCreate) -> User:
        # Check if department exists
        dept = self.db.query(Department).filter(Department.id == payload.department_id).first()
        if not dept:
            raise ResourceNotFoundException("Department", payload.department_id)

        # Check if username or email exists
        if self.db.query(User).filter(User.username == payload.username).first():
            raise ValidationBusinessException(detail="Username already registered")
        if self.db.query(User).filter(User.email == payload.email).first():
            raise ValidationBusinessException(detail="Email already registered")

        new_user = User(
            username=payload.username,
            email=payload.email,
            hashed_password=get_password_hash(payload.password),
            role="HOD",
            department_id=payload.department_id,
        )
        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)
        return new_user

    def list_hods(self, skip: int = 0, limit: int = 100) -> List[User]:
        return self.db.query(User).filter(User.role == "HOD").offset(skip).limit(limit).all()

    def get_hod(self, hod_id: int) -> User:
        user = self.db.query(User).filter(User.id == hod_id, User.role == "HOD").first()
        if not user:
            raise ResourceNotFoundException("HOD", hod_id)
        return user

    def update_hod(self, hod_id: int, payload: HODUpdate) -> User:
        user = self.get_hod(hod_id)
        
        if payload.department_id is not None:
            dept = self.db.query(Department).filter(Department.id == payload.department_id).first()
            if not dept:
                raise ResourceNotFoundException("Department", payload.department_id)
            user.department_id = payload.department_id
            
        if payload.email is not None:
            if self.db.query(User).filter(User.email == payload.email, User.id != hod_id).first():
                raise ValidationBusinessException(detail="Email already registered")
            user.email = payload.email
            
        if payload.is_active is not None:
            user.is_active = payload.is_active
            
        self.db.commit()
        self.db.refresh(user)
        return user

    def deactivate_hod(self, hod_id: int) -> User:
        user = self.get_hod(hod_id)
        user.is_active = False
        self.db.commit()
        self.db.refresh(user)
        return user

    def reset_hod_password(self, hod_id: int, new_password: str) -> User:
        user = self.get_hod(hod_id)
        user.hashed_password = get_password_hash(new_password)
        self.db.commit()
        self.db.refresh(user)
        return user
