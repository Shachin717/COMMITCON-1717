from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


RoleType = Literal["ADMIN", "HOD", "COORDINATOR", "FACULTY", "VIEWER"]


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5, max_length=100, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(..., min_length=6)
    role: RoleType = "COORDINATOR"


class HODCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5, max_length=100, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(..., min_length=6)
    department_id: int


class HODUpdate(BaseModel):
    email: Optional[str] = Field(None, min_length=5, max_length=100, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    department_id: Optional[int] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    department_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
