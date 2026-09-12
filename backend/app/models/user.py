from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey, enum_column
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.doctor import DoctorProfile
    from app.models.patient import PatientProfile


class User(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "users"

    role: Mapped[UserRole] = mapped_column(enum_column(UserRole, "user_role"), nullable=False)
    email: Mapped[str] = mapped_column(sa.String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True, server_default=sa.true())

    patient_profile: Mapped[PatientProfile | None] = relationship(back_populates="user", uselist=False)
    doctor_profile: Mapped[DoctorProfile | None] = relationship(back_populates="user", uselist=False)
