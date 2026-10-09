from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.department import DepartmentResponse


class ClassGroupBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    department_id: int
    student_count: int = Field(..., ge=0, description="Number of students in group (non-negative)")
    is_active: bool = Field(True)


class ClassGroupCreate(ClassGroupBase):
    pass


class ClassGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    department_id: Optional[int] = None
    student_count: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class ClassGroupResponse(ClassGroupBase):
    id: int
    created_at: datetime
    updated_at: datetime
    department: Optional[DepartmentResponse] = None

    model_config = ConfigDict(from_attributes=True)

