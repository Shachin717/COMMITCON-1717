from datetime import date, time
from typing import List, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.facility import FacilityResponse
from app.schemas.class_group import ClassGroupResponse


SessionStatus = Literal["ACTIVE", "CANCELLED"]
RoomType = Literal["CLASSROOM", "LAB"]


class ClassSessionBase(BaseModel):
    class_group_id: int
    session_date: date
    start_time: time
    end_time: time
    required_room_type: RoomType = Field("CLASSROOM")
    status: SessionStatus = Field("ACTIVE")
    notes: Optional[str] = Field(None, max_length=255)

    @model_validator(mode="after")
    def validate_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be strictly after start_time")
        return self


class ClassSessionCreate(ClassSessionBase):
    required_facility_ids: Optional[List[int]] = Field(default_factory=list)


class ClassSessionUpdate(BaseModel):
    class_group_id: Optional[int] = None
    session_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    required_room_type: Optional[RoomType] = None
    status: Optional[SessionStatus] = None
    notes: Optional[str] = None
    required_facility_ids: Optional[List[int]] = None

    @model_validator(mode="after")
    def validate_times(self):
        if self.start_time is not None and self.end_time is not None:
            if self.end_time <= self.start_time:
                raise ValueError("end_time must be strictly after start_time")
        return self


class ClassSessionResponse(ClassSessionBase):
    id: int
    class_group: Optional[ClassGroupResponse] = None
    required_facilities: List[FacilityResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class TimeSlotCreate(BaseModel):
    name: Optional[str] = None
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be strictly after start_time")
        return self


class TimeSlotResponse(TimeSlotCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)

