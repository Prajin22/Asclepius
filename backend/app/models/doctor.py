from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.languages import LanguageCode
from app.db.base import Base, Timestamps, UUIDPrimaryKey, enum_column
from app.models.enums import DoctorApproval

if TYPE_CHECKING:
    from app.models.user import User


class DoctorProfile(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "doctor_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    specialization: Mapped[str] = mapped_column(sa.String(120), nullable=False, index=True)
    qualification: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    # Synthetic in this prototype. An admin checks it by hand before approving;
    # there is no automated register lookup.
    registration_identifier: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    clinic_name: Mapped[str | None] = mapped_column(sa.String(200))
    clinic_address: Mapped[str | None] = mapped_column(sa.Text)
    phone: Mapped[str | None] = mapped_column(sa.String(32))
    is_accepting_consultations: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=True, server_default=sa.true()
    )
    # Self sign-ups start pending. Who reviewed is in the audit trail.
    approval_status: Mapped[DoctorApproval] = mapped_column(
        enum_column(DoctorApproval, "doctor_approval"),
        nullable=False,
        default=DoctorApproval.PENDING,
        server_default=DoctorApproval.PENDING.value,
        index=True,
    )
    # Shown to the applicant when an application is not approved.
    approval_note: Mapped[str | None] = mapped_column(sa.String(300))
    reviewed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    @property
    def is_approved(self) -> bool:
        return self.approval_status == DoctorApproval.APPROVED

    user: Mapped[User] = relationship(back_populates="doctor_profile")
    language_links: Mapped[list[DoctorLanguage]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan", order_by="DoctorLanguage.language_code"
    )

    @property
    def languages(self) -> list[LanguageCode]:
        return [link.language_code for link in self.language_links]

    def set_languages(self, codes: list[LanguageCode]) -> None:
        wanted = list(dict.fromkeys(codes))
        self.language_links = [DoctorLanguage(language_code=c) for c in wanted]


class DoctorLanguage(Base):
    __tablename__ = "doctor_languages"

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("doctor_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    language_code: Mapped[LanguageCode] = mapped_column(
        enum_column(LanguageCode, "language_code"), primary_key=True
    )

    doctor: Mapped[DoctorProfile] = relationship(back_populates="language_links")
