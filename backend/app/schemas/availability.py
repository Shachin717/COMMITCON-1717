from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, model_validator
from app.schemas.classroom import ClassroomResponse, RoomType


class AvailabilityQuery(BaseModel):
    start_datetime: datetime
    end_datetime: datetime
    student_count: Optional[int] = Field(None, ge=0)
    room_type: Optional[RoomType] = None
    department_id: Optional[int] = None
    required_facility_ids: Optional[List[int]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_datetime <= self.start_datetime:
            raise ValueError("end_datetime must be strictly after start_datetime")
        return self


class AvailableRoomItem(BaseModel):
    classroom: ClassroomResponse
    is_eligible: bool
    ineligibility_reasons: List[str] = Field(default_factory=list)
    excess_capacity: Optional[int] = None


class AvailabilityResponse(BaseModel):
    query: AvailabilityQuery
    total_eligible: int
    eligible_rooms: List[ClassroomResponse]
    evaluations: List[AvailableRoomItem]

