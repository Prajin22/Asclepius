"""IP-SAKTI product profiles and formulation classification (Phase 3, D-087–D-091).

    product_profiles           what a user says their product is (their facts)
    classification_sessions    one walk of one classifier tree version, for one product
    classification_answers     each answer, append-only: a revision supersedes, never edits
    classification_outcomes    each result the walk reached: a category, or a stop
    classifier_reference_links a curator's link from a tree's reference slot to an
                               approved provision version

Three kinds of thing, kept apart. A profile holds USER-PROVIDED facts and no
legal conclusion. An outcome is the SYSTEM's classification from the user's
answers. A reference link is CURATOR-VERIFIED only when it points at approved
corpus text. None of these tables touches a healthcare table, and no
healthcare table touches them.

Outcomes and reference links never change once written; answers change only
by being superseded; a confirmed, rejected or superseded session never changes
again. The database holds these rules with triggers, as Phase 2's corpus does.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.languages import LanguageCode
from app.db.base import Base, JSONType, Timestamps, UUIDPrimaryKey, enum_column, utcnow
from app.models.enums import (
    AdministrationRoute,
    ClassificationStatus,
    CorpusLane,
    FormulationCategory,
    OutcomeKind,
)

_OPEN = sa.text("status IN ('incomplete', 'requires_information', 'determined')")
_CURRENT = sa.text("superseded_at IS NULL")


class ProductProfile(UUIDPrimaryKey, Timestamps, Base):
    """A user's description of their product, in their own words.

    Descriptive facts only. Whether the formula matches a classical text, or
    whether its ingredients are in a schedule, are not stored here: those are
    the user's answers to the classifier's questions, recorded with the session
    that asked them. Nothing here is a legal classification.
    """

    __tablename__ = "product_profiles"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    intended_use: Mapped[str | None] = mapped_column(sa.String(2000))
    dosage_form: Mapped[str | None] = mapped_column(sa.String(200))
    administration_route: Mapped[AdministrationRoute | None] = mapped_column(
        enum_column(AdministrationRoute, "administration_route")
    )
    #: [{"name": ..., "part_used": ..., "quantity": ...}] — as the user wrote them.
    ingredients: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False, default=list)
    preparation_method: Mapped[str | None] = mapped_column(sa.String(5000))
    #: The classical text or formulation the user says they follow, by name.
    classical_reference: Mapped[str | None] = mapped_column(sa.String(300))
    extract_description: Mapped[str | None] = mapped_column(sa.String(2000))
    standardization_description: Mapped[str | None] = mapped_column(sa.String(2000))
    #: Marker compounds the user names, as written.
    markers: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(sa.String(2000))
    #: The language the free-text fields are written in. Kept as written.
    text_language: Mapped[LanguageCode | None] = mapped_column(enum_column(LanguageCode, "product_text_language"))
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)

    __mapper_args__ = {"version_id_col": revision}


class ClassificationSession(UUIDPrimaryKey, Timestamps, Base):
    """One walk of one classifier tree version for one product.

    The tree id, version and fingerprint are fixed when the session starts, and
    the product's profile is copied as it stood, so the session can always be
    read back exactly as it was. Restarting makes a new session; this one stays.
    """

    __tablename__ = "classification_sessions"
    __table_args__ = (
        # One open session per product, held by the database.
        sa.Index("uq_classification_sessions_one_open", "product_id", unique=True,
                 postgresql_where=_OPEN, sqlite_where=_OPEN),
        sa.CheckConstraint(
            "status NOT IN ('user_confirmed', 'user_rejected') OR "
            "(decided_at IS NOT NULL AND decided_by_user_id IS NOT NULL AND decided_outcome_id IS NOT NULL)",
            name="decision_recorded",
        ),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("product_profiles.id"), nullable=False, index=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("users.id"), nullable=False, index=True)
    classifier_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    tree_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    tree_fingerprint: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    status: Mapped[ClassificationStatus] = mapped_column(
        enum_column(ClassificationStatus, "classification_status"),
        nullable=False,
        default=ClassificationStatus.INCOMPLETE,
        server_default=ClassificationStatus.INCOMPLETE.value,
        index=True,
    )
    #: The question waiting ("incomplete"), or the one answered "unknown" ("requires_information").
    current_node_id: Mapped[str | None] = mapped_column(sa.String(64))
    product_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    product_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    restarted_from_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("classification_sessions.id", name="fk_classification_sessions_restarted_from")
    )
    #: The user's decision on a determined result, and which outcome it was about.
    decided_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("users.id"))
    #: Not a foreign key: outcomes already point at their session, and a cycle of
    #: keys would complicate every write. The service checks it is this session's
    #: latest outcome before recording a decision.
    decided_outcome_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid)
    rejection_reason: Mapped[str | None] = mapped_column(sa.String(1000))
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)

    __mapper_args__ = {"version_id_col": revision}


class ClassificationAnswer(UUIDPrimaryKey, Base):
    """One answer to one question. Revising it supersedes this row; nothing is edited."""

    __tablename__ = "classification_answers"
    __table_args__ = (
        sa.Index("uq_classification_answers_current", "session_id", "node_id", unique=True,
                 postgresql_where=_CURRENT, sqlite_where=_CURRENT),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("classification_sessions.id"), nullable=False, index=True
    )
    node_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    choice: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    answered_by_user_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("users.id"), nullable=False)
    answered_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow, server_default=sa.func.now()
    )
    superseded_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class ClassificationOutcome(UUIDPrimaryKey, Base):
    """What one walk ended in, written once and never changed.

    A determined outcome has a category; a stop has the question answered
    "unknown" and no category — the database refuses anything else. `path`,
    the tree fingerprint and the answers' hash make the result reproducible,
    and `references` records each reference slot's status when it was reached.
    """

    __tablename__ = "classification_outcomes"
    __table_args__ = (
        sa.UniqueConstraint("session_id", "sequence", name="uq_classification_outcomes_sequence"),
        sa.CheckConstraint(
            "(kind = 'determined' AND category IS NOT NULL AND stop_node_id IS NULL) OR "
            "(kind = 'requires_information' AND category IS NULL AND stop_node_id IS NOT NULL)",
            name="category_only_when_determined",
        ),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("classification_sessions.id"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    kind: Mapped[OutcomeKind] = mapped_column(enum_column(OutcomeKind, "outcome_kind"), nullable=False)
    category: Mapped[FormulationCategory | None] = mapped_column(
        enum_column(FormulationCategory, "formulation_category"), index=True
    )
    stop_node_id: Mapped[str | None] = mapped_column(sa.String(64))
    #: [[node_id, choice], ...] in the order walked.
    path: Mapped[list[list[str]]] = mapped_column(JSONType, nullable=False)
    answers_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    tree_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    tree_fingerprint: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    #: [{"slot_id", "status", "provision_version_id"}] as they stood when reached.
    references: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow, server_default=sa.func.now()
    )


class ClassifierReferenceLink(UUIDPrimaryKey, Base):
    """A curator's link from one reference slot of one tree version to approved corpus text.

    Append-only: the latest link for a slot is the current one. The composite
    foreign key holds the provision version to the slot's lane.
    """

    __tablename__ = "classifier_reference_links"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["provision_version_id", "lane"], ["provision_versions.id", "provision_versions.lane"],
            name="fk_classifier_reference_links_version_lane",
        ),
        sa.Index("ix_classifier_reference_links_slot", "classifier_id", "tree_version", "slot_id", "created_at"),
    )

    classifier_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    tree_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    slot_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    provision_version_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False, index=True)
    lane: Mapped[CorpusLane] = mapped_column(enum_column(CorpusLane, "corpus_lane"), nullable=False)
    linked_by_user_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow, server_default=sa.func.now()
    )


# ---------------------------------------------------------------------------
# Final rows stay final, held by the database
# ---------------------------------------------------------------------------
IMMUTABLE_ROWS: tuple[tuple[str, str | None], ...] = (
    ("classification_outcomes", None),
    ("classifier_reference_links", None),
    ("classification_sessions", "OLD.status IN ('user_confirmed', 'user_rejected', 'superseded')"),
    (
        "classification_answers",
        "OLD.superseded_at IS NOT NULL OR NEW.choice <> OLD.choice OR NEW.node_id <> OLD.node_id "
        "OR NEW.session_id <> OLD.session_id",
    ),
)


PG_REFUSE_FUNCTION = """
CREATE OR REPLACE FUNCTION sakti_refuse_final_update() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'record in % is final and cannot be changed', TG_TABLE_NAME
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$ LANGUAGE plpgsql
"""


def final_row_ddl(table: str, condition: str | None, dialect: str) -> list[str]:
    """The trigger statements that refuse an UPDATE of a final row of `table`."""
    name = f"trg_{table}_final"
    if dialect == "postgresql":
        when = f" WHEN ({condition})" if condition else ""
        return [
            PG_REFUSE_FUNCTION,
            f"CREATE TRIGGER {name} BEFORE UPDATE ON {table} FOR EACH ROW{when} "
            "EXECUTE FUNCTION sakti_refuse_final_update()",
        ]
    if dialect == "sqlite":
        when = f" WHEN {condition}" if condition else ""
        return [
            f"CREATE TRIGGER {name} BEFORE UPDATE ON {table} FOR EACH ROW{when} "
            f"BEGIN SELECT RAISE(ABORT, 'record in {table} is final and cannot be changed'); END"
        ]
    return []


for _table, _condition in IMMUTABLE_ROWS:
    for _dialect in ("postgresql", "sqlite"):
        for _statement in final_row_ddl(_table, _condition, _dialect):
            # sa.DDL formats its statement with %, so a literal % is written %%.
            _ddl = sa.DDL(_statement.replace("%", "%%"))
            sa.event.listen(Base.metadata.tables[_table], "after_create", _ddl.execute_if(dialect=_dialect))
