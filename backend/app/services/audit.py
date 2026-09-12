import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent, User


@dataclass(frozen=True)
class RequestContext:
    ip_address: str | None = None


def record(
    db: Session,
    *,
    actor: User | None,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | str | None = None,
    patient_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
    ctx: RequestContext | None = None,
) -> None:
    """Add an audit event to the current transaction (committed with the change it describes).

    Only ids/categories go in `details` — never clinical free text.
    """
    db.add(
        AuditEvent(
            actor_user_id=actor.id if actor else None,
            actor_role=actor.role.value if actor else None,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            patient_id=patient_id,
            details=details or {},
            ip_address=ctx.ip_address if ctx else None,
        )
    )
