from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class BuildingBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Building name or block")
    location: Optional[str] = Field(None, max_length=255, description="Campus location or description")


class BuildingCreate(BuildingBase):
    pass


class BuildingUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    location: Optional[str] = Field(None, max_length=255)


class BuildingResponse(BuildingBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

