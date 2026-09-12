"""doctor approval

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-12 19:40:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0006'
down_revision: str | None = '0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('doctor_profiles', sa.Column('approval_status', sa.Enum('pending', 'approved', 'rejected', name='doctor_approval', native_enum=False, create_constraint=True, length=32), server_default='pending', nullable=False))
    op.add_column('doctor_profiles', sa.Column('approval_note', sa.String(length=300), nullable=True))
    op.add_column('doctor_profiles', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_doctor_profiles_approval_status'), 'doctor_profiles', ['approval_status'], unique=False)
    # Every doctor before this revision was onboarded by an admin, so they were
    # vetted already. Only self sign-ups from here on start pending.
    op.execute("UPDATE doctor_profiles SET approval_status = 'approved', reviewed_at = now()")


def downgrade() -> None:
    # Without the column every doctor account would have full access, so
    # accounts that were never approved are switched off rather than let in.
    op.execute(
        "UPDATE users SET is_active = false WHERE id IN "
        "(SELECT user_id FROM doctor_profiles WHERE approval_status <> 'approved')"
    )
    op.drop_index(op.f('ix_doctor_profiles_approval_status'), table_name='doctor_profiles')
    op.drop_column('doctor_profiles', 'reviewed_at')
    op.drop_column('doctor_profiles', 'approval_note')
    op.drop_column('doctor_profiles', 'approval_status')
