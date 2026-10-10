from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class TimetableEntryBase(BaseModel):
    room_id: int
    day_of_week: int
    slot_id: int
    department_id: int
    subject: str
    faculty_name: str


class TimetableEntryCreate(TimetableEntryBase):
    pass


class TimetableEntryUpdate(BaseModel):
    room_id: Optional[int] = None
    day_of_week: Optional[int] = None
    slot_id: Optional[int] = None
    department_id: Optional[int] = None
    subject: Optional[str] = None
    faculty_name: Optional[str] = None


class TimetableEntryResponse(TimetableEntryBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class TimetableImportResponse(BaseModel):
    total_rows: int
    imported: int
    failed: int
    errors: List[Dict[str, Any]] = []
