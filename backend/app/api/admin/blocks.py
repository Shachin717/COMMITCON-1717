import math
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.block import (
    BlockCoordinatorAssign,
    BlockCreate,
    BlockResponse,
    BlockUpdate,
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.admin import (
    assign_coordinator_to_block,
    create_block,
    delete_block,
    get_block_by_id,
    list_blocks,
    unassign_coordinator_from_block,
    update_block,
)

router = APIRouter(prefix="/blocks", tags=["Admin Blocks"])


@router.post(
    "",
    response_model=BlockResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new physical block",
)
def create_block_route(
    data: BlockCreate,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    block = create_block(db, data, actor_id=current_admin.id)
    return BlockResponse.model_validate(block)


@router.get(
    "",
    response_model=PaginatedResponse[BlockResponse],
    summary="List blocks with assigned coordinators",
)
def list_blocks_route(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search by block name or description"),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    items, total = list_blocks(db, page=page, page_size=page_size, search=search)
    pages = math.ceil(total / page_size) if page_size > 0 else 0
    return PaginatedResponse(
        items=[BlockResponse.model_validate(b) for b in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/{block_id}",
    response_model=BlockResponse,
    summary="Get block by ID with coordinators",
)
def get_block_route(
    block_id: int,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    block = get_block_by_id(db, block_id)
    return BlockResponse.model_validate(block)


@router.put(
    "/{block_id}",
    response_model=BlockResponse,
    summary="Update block details",
)
@router.patch(
    "/{block_id}",
    response_model=BlockResponse,
    summary="Update block details",
)
def update_block_route(
    block_id: int,
    data: BlockUpdate,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    block = update_block(db, block_id, data, actor_id=current_admin.id)
    return BlockResponse.model_validate(block)


@router.delete(
    "/{block_id}",
    response_model=MessageResponse,
    summary="Delete block",
)
def delete_block_route(
    block_id: int,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    delete_block(db, block_id, actor_id=current_admin.id)
    return MessageResponse(message=f"Block {block_id} deleted successfully")


@router.post(
    "/{block_id}/coordinators",
    response_model=BlockResponse,
    summary="Assign coordinator to block",
)
def assign_coordinator_route(
    block_id: int,
    data: BlockCoordinatorAssign,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    block = assign_coordinator_to_block(
        db, block_id=block_id, user_id=data.user_id, actor_id=current_admin.id
    )
    return BlockResponse.model_validate(block)


@router.delete(
    "/{block_id}/coordinators/{user_id}",
    response_model=BlockResponse,
    summary="Unassign coordinator from block",
)
def unassign_coordinator_route(
    block_id: int,
    user_id: int,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    block = unassign_coordinator_from_block(
        db, block_id=block_id, user_id=user_id, actor_id=current_admin.id
    )
    return BlockResponse.model_validate(block)

