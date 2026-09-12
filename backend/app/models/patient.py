from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.languages import LanguageCode
from app.db.base import Base, Timestamps, UUIDPrimaryKey, enum_column
from app.models.enums import Sex

if TYPE_CHECKING:
    from app.models.user import User


class PatientProfile(UUIDPrimaryKey, Timestamps, Base):
    """Minimal personal information. Do not add fields without a clinical-communication need."""

    __tablename__ = "patient_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    display_name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(sa.Date)
    sex: Mapped[Sex] = mapped_column(
        enum_column(Sex, "sex"), nullable=False, default=Sex.UNDISCLOSED, server_default=Sex.UNDISCLOSED.value
    )
    phone: Mapped[str | None] = mapped_column(sa.String(32))
    preferred_language: Mapped[LanguageCode] = mapped_column(
        enum_column(LanguageCode, "preferred_language"),
        nullable=False,
        default=LanguageCode.EN,
        server_default=LanguageCode.EN.value,
    )
    emergency_contact_name: Mapped[str | None] = mapped_column(sa.String(120))
    emergency_contact_phone: Mapped[str | None] = mapped_column(sa.String(32))
    emergency_notes: Mapped[str | None] = mapped_column(sa.Text)
    # Explicit opt-in before any AI processing of this patient's information,
    # including sending text to an external provider. Never assumed.
    ai_processing_consent: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    ai_consent_updated_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="patient_profile")

    def age_on(self, today: date) -> int | None:
        if self.date_of_birth is None:
            return None
        dob = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
