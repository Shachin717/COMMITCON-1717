from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.facility import FacilityResponse
from app.schemas.building import BuildingResponse


RoomType = Literal["CLASSROOM", "LAB"]


class ClassroomBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    building_id: Optional[int] = Field(None, description="Optional foreign key to building")
    capacity: int = Field(..., gt=0, description="Capacity must be a positive integer")
    room_type: RoomType = Field("CLASSROOM", description="Either CLASSROOM or LAB")
    location_description: Optional[str] = Field(None, max_length=255)
    is_active: bool = Field(True, description="Whether the room is available for scheduling")


class ClassroomCreate(ClassroomBase):
    facility_ids: Optional[List[int]] = Field(default_factory=list, description="IDs of facilities available in this room")


class ClassroomUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    building_id: Optional[int] = None
    capacity: Optional[int] = Field(None, gt=0)
    room_type: Optional[RoomType] = None
    location_description: Optional[str] = None
    is_active: Optional[bool] = None


class ClassroomResponse(ClassroomBase):
    id: int
    created_at: datetime
    updated_at: datetime
    building: Optional[BuildingResponse] = None
    facilities: List[FacilityResponse] = Field(default_factory=list)
    authorized_department_ids: List[int] = Field(default_factory=list, description="Only populated for LAB rooms")

    model_config = ConfigDict(from_attributes=True)


class LabAccessUpdate(BaseModel):
    department_ids: List[int] = Field(..., description="List of authorized department IDs for this lab")


class ClassroomFacilityAdd(BaseModel):
    facility_id: int

