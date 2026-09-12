from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONType, UUIDPrimaryKey, utcnow


class AuditEvent(UUIDPrimaryKey, Base):
    """Append-only log of access to and changes of patient data.

    `patient_id` deliberately has no FK so the log outlives deleted records.
    Never store clinical content in `details` — ids and categories only.
    """

    __tablename__ = "audit_events"

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid, index=True)
    actor_role: Mapped[str | None] = mapped_column(sa.String(16))
    action: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(sa.String(64))
    patient_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid, index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(sa.String(64))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow, server_default=sa.func.now(), index=True
    )
