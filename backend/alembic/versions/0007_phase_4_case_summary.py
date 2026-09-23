"""phase 4 case summary

Adds `consultation_summaries`. No existing table changes, so Phases 1-3 behave
identically with or without this revision applied.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-23 10:20:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# JSONB on PostgreSQL, plain JSON elsewhere — matches `app.db.base.JSONType`.
_JSON = sa.JSON().with_variant(JSONB(), 'postgresql')


revision: str = '0007'
down_revision: str | None = '0006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LANGUAGES = ('en', 'hi', 'ta', 'te', 'kn', 'ml', 'mr', 'bn', 'gu', 'pa', 'or', 'as')


def upgrade() -> None:
    op.create_table(
        'consultation_summaries',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('consultation_id', sa.Uuid(), nullable=False),
        sa.Column('patient_id', sa.Uuid(), nullable=False),
        sa.Column('doctor_id', sa.Uuid(), nullable=False),
        sa.Column('artifact_id', sa.Uuid(), nullable=True),
        sa.Column('source_bundle_hash', sa.String(length=64), nullable=False),
        sa.Column('prompt_version', sa.String(length=64), nullable=True),
        sa.Column('provider', sa.String(length=64), nullable=False),
        sa.Column('model', sa.String(length=128), nullable=False),
        sa.Column(
            'status',
            sa.Enum(
                'generating', 'ready', 'failed',
                name='summary_status', native_enum=False, create_constraint=True, length=32,
            ),
            server_default='generating',
            nullable=False,
        ),
        sa.Column(
            'language',
            sa.Enum(
                *_LANGUAGES,
                name='summary_language', native_enum=False, create_constraint=True, length=32,
            ),
            server_default='en',
            nullable=False,
        ),
        sa.Column('summary', _JSON, nullable=False),
        sa.Column('dropped_item_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('warnings', _JSON, nullable=False),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['consultation_id'], ['consultations.id'],
            name=op.f('fk_consultation_summaries_consultation_id_consultations'), ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['patient_id'], ['patient_profiles.id'],
            name=op.f('fk_consultation_summaries_patient_id_patient_profiles'), ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['doctor_id'], ['doctor_profiles.id'],
            name=op.f('fk_consultation_summaries_doctor_id_doctor_profiles'), ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['artifact_id'], ['ai_artifacts.id'],
            name=op.f('fk_consultation_summaries_artifact_id_ai_artifacts'), ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_consultation_summaries')),
    )
    op.create_index(
        op.f('ix_consultation_summaries_consultation_id'),
        'consultation_summaries', ['consultation_id'], unique=False,
    )
    op.create_index(
        op.f('ix_consultation_summaries_patient_id'),
        'consultation_summaries', ['patient_id'], unique=False,
    )
    op.create_index(
        'ix_consultation_summaries_consultation_created',
        'consultation_summaries', ['consultation_id', 'created_at'], unique=False,
    )
    op.create_index(
        'ix_consultation_summaries_bundle',
        'consultation_summaries', ['consultation_id', 'source_bundle_hash'], unique=False,
    )


def downgrade() -> None:
    # Summaries are derived data: every source they organise still exists in its
    # own table, so dropping them loses no patient information.
    op.drop_index('ix_consultation_summaries_bundle', table_name='consultation_summaries')
    op.drop_index('ix_consultation_summaries_consultation_created', table_name='consultation_summaries')
    op.drop_index(op.f('ix_consultation_summaries_patient_id'), table_name='consultation_summaries')
    op.drop_index(op.f('ix_consultation_summaries_consultation_id'), table_name='consultation_summaries')
    op.drop_table('consultation_summaries')
