from datetime import date
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.enums import RoomBlockReason


class RoomBlockBase(BaseModel):
    room_id: int
    date: date
    slot_id: Optional[int] = None
    reason: RoomBlockReason
    note: Optional[str] = None


class RoomBlockCreate(RoomBlockBase):
    pass


class RoomBlockResponse(RoomBlockBase):
    id: int
    created_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

