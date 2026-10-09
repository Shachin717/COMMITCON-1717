from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


BookingStatus = Literal["PENDING", "CONFIRMED", "CANCELLED", "PENDING_HOD_APPROVAL", "APPROVED", "REJECTED"]
BookingPurpose = Literal["REGULAR_CLASS", "EXAMINATION", "MCQ_TEST", "SEMINAR", "WORKSHOP", "EVENT", "OTHER"]


class BookingBase(BaseModel):
    room_id: int
    title: str = Field(..., min_length=1, max_length=200, description="Title or event purpose")
    start_datetime: datetime
    end_datetime: datetime
    class_session_id: Optional[int] = None
    department_id: Optional[int] = None
    purpose: Optional[BookingPurpose] = "REGULAR_CLASS"

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_datetime <= self.start_datetime:
            raise ValueError("end_datetime must be strictly after start_datetime")
        return self


class BookingCreate(BookingBase):
    status: BookingStatus = Field("CONFIRMED", description="Booking status")


class BookingUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    status: Optional[BookingStatus] = None
    department_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_datetime is not None and self.end_datetime is not None:
            if self.end_datetime <= self.start_datetime:
                raise ValueError("end_datetime must be strictly after start_datetime")
        return self


class BookingResponse(BookingBase):
    id: int
    status: BookingStatus
    requested_by_user_id: Optional[int] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoomUnavailabilityBase(BaseModel):
    room_id: int
    start_datetime: datetime
    end_datetime: datetime
    reason: str = Field(..., min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_datetime <= self.start_datetime:
            raise ValueError("end_datetime must be strictly after start_datetime")
        return self


class RoomUnavailabilityCreate(RoomUnavailabilityBase):
    force: bool = Field(False, description="Whether to proceed despite conflicts after review")


class RoomUnavailabilityResponse(RoomUnavailabilityBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UnavailabilityConflictCheckResponse(BaseModel):
    has_conflicts: bool
    conflicting_bookings: list = Field(default_factory=list)
    conflicting_allocations: list = Field(default_factory=list)
    message: str

