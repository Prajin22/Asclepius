"""phase 2 hardening subject and limits

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-12 11:55:52.352712
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RECORD_TYPES_BEFORE = ("condition", "allergy", "medication", "history_note", "current_problem")
RECORD_TYPES_AFTER = (*RECORD_TYPES_BEFORE, "family_history")


def _values(names: tuple[str, ...]) -> str:
    return ", ".join(f"'{name}'" for name in names)


def upgrade() -> None:
    op.add_column('ai_extracted_facts', sa.Column('subject', sa.Enum('self', 'family', 'other', 'unknown', name='fact_subject', native_enum=False, create_constraint=True, length=32), server_default='self', nullable=False))
    op.add_column('ai_extracted_facts', sa.Column('subject_evidence', sa.String(length=200), nullable=True))

    # Autogenerate cannot see value changes on a VARCHAR+CHECK enum, so the
    # medical_records type constraint is widened by hand for `family_history`.
    if op.get_bind().dialect.name == "postgresql":
        # op.f(): the name is already final; do not re-apply the naming convention.
        op.drop_constraint(op.f("ck_medical_records_record_type"), "medical_records", type_="check")
        op.create_check_constraint(
            op.f("ck_medical_records_record_type"), "medical_records", f"type IN ({_values(RECORD_TYPES_AFTER)})"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        # Family-history rows would violate the narrower constraint.
        op.execute("DELETE FROM medical_records WHERE type = 'family_history'")
        op.drop_constraint(op.f("ck_medical_records_record_type"), "medical_records", type_="check")
        op.create_check_constraint(
            op.f("ck_medical_records_record_type"), "medical_records", f"type IN ({_values(RECORD_TYPES_BEFORE)})"
        )
    op.drop_column('ai_extracted_facts', 'subject_evidence')
    op.drop_column('ai_extracted_facts', 'subject')
