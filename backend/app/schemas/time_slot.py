from datetime import time
from typing import Optional
from pydantic import BaseModel, ConfigDict


class TimeSlotBase(BaseModel):
    label: str
    start_time: time
    end_time: time
    order: int = 1


class TimeSlotCreate(TimeSlotBase):
    pass


class TimeSlotUpdate(BaseModel):
    label: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    order: Optional[int] = None


class TimeSlotResponse(TimeSlotBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
