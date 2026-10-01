"""phase 5 conversation engine

Adds `conversation_sessions`, `conversation_responses` and
`conversation_candidate_facts`. No existing table is touched, so Phases 1-4
behave identically with or without this revision applied.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-23 16:40:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# JSONB on PostgreSQL, plain JSON elsewhere — matches `app.db.base.JSONType`.
_JSON = sa.JSON().with_variant(JSONB(), 'postgresql')


revision: str = '0008'
down_revision: str | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LANGUAGES = ('en', 'hi', 'ta', 'te', 'kn', 'ml', 'mr', 'bn', 'gu', 'pa', 'or', 'as')

_STATUSES = ('awaiting_answer', 'awaiting_confirmation', 'paused', 'completed', 'abandoned')

_SECTIONS = (
    'current_problem', 'onset_duration', 'location', 'character',
    'associated_symptoms', 'aggravating_relieving', 'relevant_history',
    'medications', 'allergies', 'review',
)

_RESPONSE_TYPES = ('free_text', 'single_choice', 'multi_choice', 'yes_no', 'duration')

_CATEGORIES = ('symptom', 'duration', 'medication', 'allergy', 'medical_history', 'measurement')

_SUBJECTS = ('self', 'family', 'other', 'unknown')

_REVIEW_STATES = ('pending', 'confirmed', 'edited', 'rejected')


def _enum(values: tuple[str, ...], name: str) -> sa.Enum:
    """VARCHAR + CHECK, matching `app.db.base.enum_column`."""
    return sa.Enum(
        *values, name=name, native_enum=False, create_constraint=True, length=32
    )


def upgrade() -> None:
    op.create_table(
        'conversation_sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('patient_id', sa.Uuid(), nullable=False),
        sa.Column('flow_id', sa.String(length=64), nullable=False),
        sa.Column('flow_version', sa.Integer(), nullable=False),
        sa.Column(
            'status', _enum(_STATUSES, 'conversation_status'),
            server_default='awaiting_answer', nullable=False,
        ),
        sa.Column(
            'language', _enum(_LANGUAGES, 'conversation_language'),
            server_default='en', nullable=False,
        ),
        sa.Column('current_section', _enum(_SECTIONS, 'conversation_section'), nullable=True),
        sa.Column('current_question_id', sa.String(length=64), nullable=True),
        sa.Column('current_question_version', sa.Integer(), nullable=True),
        sa.Column('current_question_reason', sa.String(length=300), nullable=True),
        sa.Column('revision', sa.Integer(), server_default='0', nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['patient_id'], ['patient_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_conversation_sessions_patient_id'), 'conversation_sessions', ['patient_id']
    )
    op.create_index(
        'ix_conversation_sessions_patient_status',
        'conversation_sessions',
        ['patient_id', 'status'],
    )

    op.create_table(
        'conversation_responses',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('session_id', sa.Uuid(), nullable=False),
        sa.Column('patient_id', sa.Uuid(), nullable=False),
        sa.Column('question_id', sa.String(length=64), nullable=False),
        sa.Column('question_version', sa.Integer(), nullable=False),
        sa.Column('section', _enum(_SECTIONS, 'response_section'), nullable=False),
        sa.Column('response_type', _enum(_RESPONSE_TYPES, 'response_type'), nullable=False),
        sa.Column('answer_text', sa.Text(), nullable=True),
        sa.Column('answer_language', _enum(_LANGUAGES, 'answer_language'), nullable=True),
        sa.Column('answer_value', _JSON, nullable=False),
        sa.Column('skipped', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('idempotency_key', sa.String(length=64), nullable=False),
        sa.Column('superseded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['conversation_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patient_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        # A retried submission is the same answer, not a second one.
        sa.UniqueConstraint('session_id', 'idempotency_key', name='uq_conversation_response_idempotency'),
    )
    op.create_index(
        op.f('ix_conversation_responses_session_id'), 'conversation_responses', ['session_id']
    )
    op.create_index(
        op.f('ix_conversation_responses_patient_id'), 'conversation_responses', ['patient_id']
    )
    op.create_index(
        'ix_conversation_responses_session_current',
        'conversation_responses',
        ['session_id', 'superseded_at'],
    )

    op.create_table(
        'conversation_candidate_facts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('session_id', sa.Uuid(), nullable=False),
        sa.Column('response_id', sa.Uuid(), nullable=False),
        sa.Column('patient_id', sa.Uuid(), nullable=False),
        sa.Column('category', _enum(_CATEGORIES, 'candidate_category'), nullable=False),
        sa.Column(
            'subject', _enum(_SUBJECTS, 'candidate_subject'),
            server_default='self', nullable=False,
        ),
        sa.Column('subject_evidence', sa.String(length=200), nullable=True),
        sa.Column('value', sa.String(length=300), nullable=False),
        sa.Column('original_text', sa.Text(), nullable=True),
        sa.Column(
            'review_state', _enum(_REVIEW_STATES, 'candidate_review_state'),
            server_default='pending', nullable=False,
        ),
        sa.Column('edited_value', sa.String(length=300), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_by_user_id', sa.Uuid(), nullable=True),
        sa.Column('medical_record_id', sa.Uuid(), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['conversation_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['response_id'], ['conversation_responses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patient_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['medical_record_id'], ['medical_records.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_conversation_candidate_facts_session_id'),
        'conversation_candidate_facts', ['session_id'],
    )
    op.create_index(
        op.f('ix_conversation_candidate_facts_response_id'),
        'conversation_candidate_facts', ['response_id'],
    )
    op.create_index(
        op.f('ix_conversation_candidate_facts_patient_id'),
        'conversation_candidate_facts', ['patient_id'],
    )
    op.create_index(
        'ix_conversation_candidates_session_state',
        'conversation_candidate_facts',
        ['session_id', 'review_state'],
    )


def downgrade() -> None:
    # Dropped in dependency order: candidates reference responses reference
    # sessions. Health records confirmed out of a conversation are not touched —
    # they are the patient's, and they stand on their own.
    op.drop_index('ix_conversation_candidates_session_state', table_name='conversation_candidate_facts')
    op.drop_index(
        op.f('ix_conversation_candidate_facts_patient_id'), table_name='conversation_candidate_facts'
    )
    op.drop_index(
        op.f('ix_conversation_candidate_facts_response_id'), table_name='conversation_candidate_facts'
    )
    op.drop_index(
        op.f('ix_conversation_candidate_facts_session_id'), table_name='conversation_candidate_facts'
    )
    op.drop_table('conversation_candidate_facts')

    op.drop_index('ix_conversation_responses_session_current', table_name='conversation_responses')
    op.drop_index(op.f('ix_conversation_responses_patient_id'), table_name='conversation_responses')
    op.drop_index(op.f('ix_conversation_responses_session_id'), table_name='conversation_responses')
    op.drop_table('conversation_responses')

    op.drop_index('ix_conversation_sessions_patient_status', table_name='conversation_sessions')
    op.drop_index(op.f('ix_conversation_sessions_patient_id'), table_name='conversation_sessions')
    op.drop_table('conversation_sessions')
