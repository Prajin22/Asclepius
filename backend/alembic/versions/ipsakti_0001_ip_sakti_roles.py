"""ip-sakti roles on the shared users table

The only schema change IP-SAKTI Sahayak's Phase 1 makes, and the only one it
makes to a table CareBridge also uses: `users.role` accepts the IP-SAKTI
roles — user, facilitator, curator — beside CareBridge's patient, doctor and
admin (D-078). Which of them a running application accepts is decided by its
PRODUCT, not by the schema.

No healthcare table is touched. `consultations.cancelled_by_role` and
`consultation_messages.sender_role` keep exactly the constraint 0001 gave them.

Written by hand: autogenerate cannot see value changes on a VARCHAR + CHECK
enum (as in 0003 and 0009), so `alembic check` passing says nothing about it.
The migration tests read the constraint back from PostgreSQL instead.

The revision id carries an `ipsakti_` prefix, so a CareBridge revision added
after 0009 on another branch cannot collide with it; joining the two later is
an explicit merge revision. No Alembic branch label: on a linear chain Alembic
applies a label to every ancestor too, which would mark CareBridge's own
revisions as IP-SAKTI's.

Revision ID: ipsakti_0001
Revises: 0009
Create Date: 2026-10-01 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'ipsakti_0001'
down_revision: str | None = '0009'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLES_BEFORE = ('patient', 'doctor', 'admin')
_ROLES_AFTER = ('patient', 'doctor', 'admin', 'user', 'facilitator', 'curator')
_IP_SAKTI_ONLY = ('user', 'facilitator', 'curator')

_CONSTRAINT = 'ck_users_user_role'


def _values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _set_role_check(values: tuple[str, ...]) -> None:
    if op.get_bind().dialect.name != 'postgresql':
        return
    # op.f(): the name is already final; do not re-apply the naming convention.
    op.drop_constraint(op.f(_CONSTRAINT), 'users', type_='check')
    op.create_check_constraint(op.f(_CONSTRAINT), 'users', f"role IN ({_values(values)})")


def upgrade() -> None:
    _set_role_check(_ROLES_AFTER)


def downgrade() -> None:
    # An IP-SAKTI account cannot be represented once its role is no longer
    # valid. Deleting it would delete a person's account as a side effect of a
    # schema change, so the downgrade stops instead (the rule 0009 follows).
    count = op.get_bind().execute(
        sa.text(f"SELECT COUNT(*) FROM users WHERE role IN ({_values(_IP_SAKTI_ONLY)})")
    ).scalar()
    if count:
        raise RuntimeError(
            f"Refusing to downgrade ipsakti_0001: {count} account(s) hold an IP-SAKTI role "
            f"({', '.join(_IP_SAKTI_ONLY)}). Remove them deliberately first. Nothing has been changed."
        )
    _set_role_check(_ROLES_BEFORE)
