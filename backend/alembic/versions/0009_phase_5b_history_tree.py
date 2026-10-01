"""phase 5b deterministic history tree

Adds what the history_general v2 tree needs, on top of 0008:

* `conversation_skips` — questions the engine did not ask, and why. Never an
  answer: "not asked" is recorded here so that it is never mistaken for "no".
* `conversation_responses.skipped` renamed `declined` — it always meant "the
  patient chose not to answer", and the tree now also has "not applicable",
  which must not share its name.
* reason code, trigger and predicate columns on responses and the session, so
  every question asked can say why without any English being stored.
* `conversation_candidate_facts.superseded_at`, so revising an answer retires
  what it suggested rather than deleting it.
* at most one *current* answer, and one current skip, per question per session,
  enforced by partial unique indexes.
* at most one open conversation per patient, enforced by a partial unique
  index — 0008 only checked in Python, so two simultaneous starts could both
  pass the check and leave a patient with two half-finished histories.
* three new section values, widened by hand on PostgreSQL because autogenerate
  cannot see value changes on a VARCHAR + CHECK enum (the same reason as 0003).

No Phase 1-4 table is touched.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-24 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0009'
down_revision: str | None = '0008'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SECTIONS_BEFORE = (
    'current_problem', 'onset_duration', 'location', 'character',
    'associated_symptoms', 'aggravating_relieving', 'relevant_history',
    'medications', 'allergies', 'review',
)
_SECTIONS_AFTER = (
    'current_problem', 'onset_duration', 'location', 'character',
    'radiation_or_spread', 'associated_symptoms', 'aggravating_relieving',
    'aggravating_factors', 'relieving_factors', 'relevant_history',
    'medications', 'allergies', 'review',
)

# (table, constraint, column) for every section CHECK that 0008 created.
_SECTION_CHECKS = (
    ('conversation_sessions', 'ck_conversation_sessions_conversation_section', 'current_section'),
    ('conversation_responses', 'ck_conversation_responses_response_section', 'section'),
)

_CURRENT = sa.text('superseded_at IS NULL')
_OPEN = sa.text("status IN ('awaiting_answer', 'awaiting_confirmation', 'paused')")


def _values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _set_section_checks(values: tuple[str, ...]) -> None:
    if op.get_bind().dialect.name != 'postgresql':
        return
    for table, name, column in _SECTION_CHECKS:
        # op.f(): the name is already final; do not re-apply the naming convention.
        op.drop_constraint(op.f(name), table, type_='check')
        op.create_check_constraint(op.f(name), table, f"{column} IN ({_values(values)})")


def upgrade() -> None:
    _set_section_checks(_SECTIONS_AFTER)

    op.alter_column('conversation_responses', 'skipped', new_column_name='declined')
    op.add_column('conversation_responses', sa.Column('reason_code', sa.String(length=64), nullable=True))
    op.add_column('conversation_responses', sa.Column('trigger_question_id', sa.String(length=64), nullable=True))
    op.add_column('conversation_responses', sa.Column('predicate_id', sa.String(length=64), nullable=True))
    op.create_index(
        'uq_conversation_responses_current_answer',
        'conversation_responses',
        ['session_id', 'question_id'],
        unique=True,
        postgresql_where=_CURRENT,
        sqlite_where=_CURRENT,
    )

    op.create_index(
        'uq_conversation_sessions_one_open',
        'conversation_sessions',
        ['patient_id'],
        unique=True,
        postgresql_where=_OPEN,
        sqlite_where=_OPEN,
    )
    op.add_column('conversation_sessions', sa.Column('current_trigger_question_id', sa.String(length=64), nullable=True))
    op.add_column('conversation_sessions', sa.Column('current_predicate_id', sa.String(length=64), nullable=True))

    op.add_column(
        'conversation_candidate_facts',
        sa.Column('superseded_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        'conversation_skips',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('session_id', sa.Uuid(), nullable=False),
        sa.Column('patient_id', sa.Uuid(), nullable=False),
        sa.Column('question_id', sa.String(length=64), nullable=False),
        sa.Column('question_version', sa.Integer(), nullable=False),
        sa.Column('flow_version', sa.Integer(), nullable=False),
        sa.Column(
            'section',
            sa.Enum(*_SECTIONS_AFTER, name='skip_section', native_enum=False, create_constraint=True, length=32),
            nullable=False,
        ),
        sa.Column('reason_code', sa.String(length=64), nullable=False),
        sa.Column('trigger_question_id', sa.String(length=64), nullable=True),
        sa.Column('predicate_id', sa.String(length=64), nullable=True),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('superseded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['conversation_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patient_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_conversation_skips_session_id'), 'conversation_skips', ['session_id'])
    op.create_index(op.f('ix_conversation_skips_patient_id'), 'conversation_skips', ['patient_id'])
    op.create_index(
        'ix_conversation_skips_session_current', 'conversation_skips', ['session_id', 'superseded_at']
    )
    op.create_index(
        'uq_conversation_skips_current',
        'conversation_skips',
        ['session_id', 'question_id'],
        unique=True,
        postgresql_where=_CURRENT,
        sqlite_where=_CURRENT,
    )


def _refuse_if_data_would_be_misrepresented() -> None:
    """Refuse, rather than destroy or distort, what 0008 cannot hold.

    0003 deleted the rows its narrower schema could not represent. That was a
    derived record type; these are patient answers. A v2 conversation carries
    sections 0008 does not allow, and a superseded candidate would reappear as
    live under 0008's code, offered for confirmation after its answer was
    corrected. Neither is acceptable to do silently, so the downgrade stops and
    says why. Export or remove the data deliberately, then downgrade.
    """
    bind = op.get_bind()
    v2_sessions = bind.execute(sa.text('SELECT COUNT(*) FROM conversation_sessions WHERE flow_version >= 2')).scalar()
    superseded = bind.execute(
        sa.text('SELECT COUNT(*) FROM conversation_candidate_facts WHERE superseded_at IS NOT NULL')
    ).scalar()
    if v2_sessions or superseded:
        raise RuntimeError(
            f"Refusing to downgrade 0009: {v2_sessions} history_general v2 conversation(s) and "
            f"{superseded} superseded candidate(s) cannot be represented by 0008 without "
            "destroying or misrepresenting patient answers. Nothing has been changed."
        )


def downgrade() -> None:
    _refuse_if_data_would_be_misrepresented()

    op.drop_index('uq_conversation_skips_current', table_name='conversation_skips')
    op.drop_index('ix_conversation_skips_session_current', table_name='conversation_skips')
    op.drop_index(op.f('ix_conversation_skips_patient_id'), table_name='conversation_skips')
    op.drop_index(op.f('ix_conversation_skips_session_id'), table_name='conversation_skips')
    op.drop_table('conversation_skips')

    op.drop_column('conversation_candidate_facts', 'superseded_at')

    op.drop_column('conversation_sessions', 'current_predicate_id')
    op.drop_index('uq_conversation_sessions_one_open', table_name='conversation_sessions')
    op.drop_column('conversation_sessions', 'current_trigger_question_id')

    op.drop_index('uq_conversation_responses_current_answer', table_name='conversation_responses')
    op.drop_column('conversation_responses', 'predicate_id')
    op.drop_column('conversation_responses', 'trigger_question_id')
    op.drop_column('conversation_responses', 'reason_code')
    op.alter_column('conversation_responses', 'declined', new_column_name='skipped')

    _set_section_checks(_SECTIONS_BEFORE)
