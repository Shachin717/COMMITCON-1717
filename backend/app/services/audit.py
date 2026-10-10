from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_audit(
    db: Session,
    action: str,
    entity: str,
    entity_id: Optional[Any] = None,
    actor_id: Optional[int] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """Record an audit trail entry in the database."""
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        meta=meta or {},
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

