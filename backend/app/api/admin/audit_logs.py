import math
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.audit_log import AuditLogResponse
from app.schemas.common import PaginatedResponse
from app.services.admin import list_audit_logs

router = APIRouter(prefix="/audit-logs", tags=["Admin Audit Logs"])


@router.get(
    "",
    response_model=PaginatedResponse[AuditLogResponse],
    summary="View system audit trail logs with filtering, search, and pagination",
)
def list_audit_logs_route(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    actor_id: Optional[int] = Query(None, description="Filter by actor user ID"),
    action: Optional[str] = Query(None, description="Filter by action name"),
    entity: Optional[str] = Query(None, description="Filter by entity type (User, Room, etc.)"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
    start_date: Optional[datetime] = Query(None, description="Filter logs starting at datetime"),
    end_date: Optional[datetime] = Query(None, description="Filter logs ending at datetime"),
    search: Optional[str] = Query(None, description="Search across action, entity, entity_id"),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    items, total = list_audit_logs(
        db,
        page=page,
        page_size=page_size,
        actor_id=actor_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date,
        search=search,
    )
    pages = math.ceil(total / page_size) if page_size > 0 else 0
    return PaginatedResponse(
        items=[AuditLogResponse.model_validate(log) for log in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )

