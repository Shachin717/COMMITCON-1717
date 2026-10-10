from typing import Optional
from pydantic import BaseModel, ConfigDict


class FacilityBase(BaseModel):
    name: str


class FacilityCreate(FacilityBase):
    pass


class FacilityUpdate(BaseModel):
    name: Optional[str] = None


class FacilityResponse(FacilityBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
