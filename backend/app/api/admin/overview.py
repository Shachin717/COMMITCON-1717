from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.overview import AdminOverviewResponse
from app.services.admin import get_admin_overview

router = APIRouter(prefix="/overview", tags=["Admin Overview"])


@router.get(
    "",
    response_model=AdminOverviewResponse,
    summary="Get aggregated administrator dashboard overview statistics, utilization, and charts",
)
def get_admin_overview_route(
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return get_admin_overview(db)

