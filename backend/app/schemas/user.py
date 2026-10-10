from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr
from app.models.enums import UserRole


class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: UserRole
    department_id: Optional[int] = None
    phone: Optional[str] = None
    is_active: bool = True
    must_change_password: bool = False


class UserCreate(UserBase):
    password: str


class AdminUserCreate(BaseModel):
    name: str
    email: EmailStr
    role: UserRole
    department_id: Optional[int] = None
    phone: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    department_id: Optional[int] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    must_change_password: Optional[bool] = None
    password: Optional[str] = None


class UserResponse(UserBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserCreateResponse(UserResponse):
    temporary_password: Optional[str] = None
