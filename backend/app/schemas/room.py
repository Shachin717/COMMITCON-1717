from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.models.enums import RoomStatus, RoomType
from app.schemas.facility import FacilityResponse


class RoomBase(BaseModel):
    name: str
    block_id: int
    floor: int
    room_type: RoomType
    capacity: int
    department_id: Optional[int] = None
    status: RoomStatus = RoomStatus.ACTIVE
    maintenance_note: Optional[str] = None


class RoomCreate(RoomBase):
    facility_ids: Optional[List[int]] = None


class RoomUpdate(BaseModel):
    name: Optional[str] = None
    block_id: Optional[int] = None
    floor: Optional[int] = None
    room_type: Optional[RoomType] = None
    capacity: Optional[int] = None
    department_id: Optional[int] = None
    status: Optional[RoomStatus] = None
    maintenance_note: Optional[str] = None
    facility_ids: Optional[List[int]] = None


class RoomStatusUpdate(BaseModel):
    status: RoomStatus
    maintenance_note: Optional[str] = None


class RoomResponse(RoomBase):
    id: int
    facilities: List[FacilityResponse] = []

    model_config = ConfigDict(from_attributes=True)


class RoomImportResponse(BaseModel):
    total_rows: int
    imported: int
    errors: List[dict] = []

