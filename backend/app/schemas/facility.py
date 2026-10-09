from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class FacilityBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Facility name, e.g. Projector")
    description: Optional[str] = Field(None, max_length=255)


class FacilityCreate(FacilityBase):
    pass


class FacilityUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)


class FacilityResponse(FacilityBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

