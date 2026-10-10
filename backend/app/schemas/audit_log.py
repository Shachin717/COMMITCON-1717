from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    id: int
    actor_id: Optional[int] = None
    action: str
    entity: str
    entity_id: Optional[str] = None
    meta: Dict[str, Any] = {}
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

