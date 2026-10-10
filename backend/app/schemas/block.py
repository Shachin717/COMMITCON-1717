from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.user import UserResponse


class BlockBase(BaseModel):
    name: str
    description: Optional[str] = None


class BlockCreate(BlockBase):
    pass


class BlockUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class BlockResponse(BlockBase):
    id: int
    coordinators: List[UserResponse] = []

    model_config = ConfigDict(from_attributes=True)


class BlockCoordinatorAssign(BaseModel):
    user_id: int
