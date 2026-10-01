"""IP-SAKTI Sahayak's legal and regulatory source corpus (Phase 2, D-081–D-086).

    an official source file — stored exactly as uploaded, sha256 checked
    before every read
        → corpus_pages: the text read from each page, verbatim, with how it was read
        → corpus_chunks: fixed, line-bounded slices of that text, in order
        → provision_versions: one span of that text, copied character for
          character, as one version of one provision of one instrument
        → a curator reviews → approved, and immutable from then on | rejected
        → provision_status_events: an append-only record of what cited
          sources say about an approved version

Nothing in these tables is generated. Text comes from the uploaded file; every
other field is a curator's own entry about where the file came from and what it
is. No column holds a conclusion about what the law means.

Every corpus table carries `lane` (india | international), and composite foreign
keys on (id, lane) make a child's lane equal to its parent's in the database
itself, so no write — through this code or around it — can move a record across
lanes (D-082). Approved and rejected rows refuse any UPDATE, and page, chunk and
status-event rows refuse every UPDATE, through triggers that `create_all` and the
migration both install (D-084).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType, Timestamps, UUIDPrimaryKey, enum_column, utcnow
from app.models.enums import (
    CorpusDocumentType,
    CorpusLane,
    CorpusReviewState,
    IngestionState,
    InstrumentType,
    LocatorType,
    ProvisionStatus,
    SourceAuthority,
    TermsStatus,
)
from app.models.user import User

#: A row whose curator decision is final.
_FINAL = "review_state IN ('approved', 'rejected')"
_LIVE = sa.text("review_state <> 'rejected'")


def _lane() -> Mapped[CorpusLane]:
    return mapped_column(enum_column(CorpusLane, "corpus_lane"), nullable=False, index=True)


def _review_state() -> Mapped[CorpusReviewState]:
    return mapped_column(
        enum_column(CorpusReviewState, "corpus_review_state"),
        nullable=False,
        default=CorpusReviewState.DRAFT,
        server_default=CorpusReviewState.DRAFT.value,
        index=True,
    )


def _user_fk(*, nullable: bool = True) -> Mapped[Any]:
    return mapped_column(sa.ForeignKey("users.id"), nullable=nullable)


class Instrument(UUIDPrimaryKey, Timestamps, Base):
    """An Act, a set of Rules, a treaty — the thing a source document is a text of.

    Descriptive only: what it is called, what kind it is, who issued it. Nothing
    about what it requires. Its lane is fixed when it is created.
    """

    __tablename__ = "instruments"
    __table_args__ = (
        sa.UniqueConstraint("id", "lane", name="uq_instruments_id_lane"),
        sa.UniqueConstraint("lane", "instrument_type", "title", name="uq_instruments_lane_type_title"),
    )

    lane: Mapped[CorpusLane] = _lane()
    instrument_type: Mapped[InstrumentType] = mapped_column(
        enum_column(InstrumentType, "instrument_type"), nullable=False
    )
    title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    #: The body that issued it, as the source names it (a legislature, a ministry, a treaty body).
    issued_by: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    #: The curator's own note on what this record is. Never statutory text.
    description: Mapped[str | None] = mapped_column(sa.String(2000))
    created_by_user_id: Mapped[uuid.UUID] = _user_fk(nullable=False)


class CorpusDocument(UUIDPrimaryKey, Timestamps, Base):
    """One official source file, with where it came from.

    The file is kept exactly as uploaded (`storage_reference` is internal and
    never leaves the API); `sha256` proves any later read is the same bytes.
    `source_date` is the date the source itself carries, `retrieved_on` the day
    the curator obtained it — neither is a validity date, and neither is the
    approval date.
    """

    __tablename__ = "corpus_documents"
    __table_args__ = (
        sa.UniqueConstraint("id", "lane", name="uq_corpus_documents_id_lane"),
        sa.ForeignKeyConstraint(
            ["instrument_id", "lane"], ["instruments.id", "instruments.lane"], name="fk_corpus_documents_instrument_lane"
        ),
        # The same bytes cannot be in the live corpus twice.
        sa.Index("uq_corpus_documents_live_sha256", "sha256", unique=True, postgresql_where=_LIVE, sqlite_where=_LIVE),
        sa.Index("ix_corpus_documents_lane_review_state", "lane", "review_state"),
        sa.CheckConstraint("source_url IS NOT NULL OR source_reference IS NOT NULL", name="provenance_required"),
        sa.CheckConstraint(
            "review_state <> 'approved' OR (approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL)",
            name="approval_recorded",
        ),
        sa.CheckConstraint(
            "review_state <> 'rejected' OR (rejected_at IS NOT NULL AND rejected_by_user_id IS NOT NULL)",
            name="rejection_recorded",
        ),
        # Only text that was actually read can be reviewed.
        sa.CheckConstraint(
            "review_state = 'draft' OR ingestion_state IN ('parsed', 'needs_review')", name="reviewed_only_when_read"
        ),
    )

    lane: Mapped[CorpusLane] = _lane()
    instrument_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False, index=True)
    title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    source_authority: Mapped[SourceAuthority] = mapped_column(
        enum_column(SourceAuthority, "source_authority"), nullable=False
    )
    document_type: Mapped[CorpusDocumentType] = mapped_column(
        enum_column(CorpusDocumentType, "corpus_document_type"), nullable=False
    )
    #: Where the curator obtained the file. Recorded, never fetched by the server.
    source_url: Mapped[str | None] = mapped_column(sa.String(2000))
    #: A citation for the file where there is no URL (a gazette number, for instance).
    source_reference: Mapped[str | None] = mapped_column(sa.String(1000))
    source_date: Mapped[date | None] = mapped_column(sa.Date)
    retrieved_on: Mapped[date] = mapped_column(sa.Date, nullable=False)
    terms_status: Mapped[TermsStatus] = mapped_column(
        enum_column(TermsStatus, "terms_status"),
        nullable=False,
        default=TermsStatus.UNKNOWN,
        server_default=TermsStatus.UNKNOWN.value,
    )

    file_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)  # display only
    mime_type: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    storage_reference: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    uploaded_by_user_id: Mapped[uuid.UUID] = _user_fk(nullable=False)

    ingestion_state: Mapped[IngestionState] = mapped_column(
        enum_column(IngestionState, "ingestion_state"),
        nullable=False,
        default=IngestionState.UPLOADED,
        server_default=IngestionState.UPLOADED.value,
    )
    #: Why the reading needs a person to check it, as codes (ocr_text_requires_verification, ...).
    ingestion_issues: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    parse_error_code: Mapped[str | None] = mapped_column(sa.String(64))
    page_count: Mapped[int | None] = mapped_column(sa.Integer)
    #: sha256 of the document text: every page's text, in order, joined by a form feed.
    text_sha256: Mapped[str | None] = mapped_column(sa.String(64))
    text_length: Mapped[int | None] = mapped_column(sa.Integer)
    extraction_methods: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    extraction_engines: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    parsed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    parsed_by_user_id: Mapped[uuid.UUID | None] = _user_fk()

    review_state: Mapped[CorpusReviewState] = _review_state()
    submitted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    submitted_by_user_id: Mapped[uuid.UUID | None] = _user_fk()
    approved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    approved_by_user_id: Mapped[uuid.UUID | None] = _user_fk()
    issues_acknowledged: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    rejected_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    rejected_by_user_id: Mapped[uuid.UUID | None] = _user_fk()
    rejection_reason: Mapped[str | None] = mapped_column(sa.String(1000))

    instrument: Mapped[Instrument] = relationship(viewonly=True)
    uploaded_by: Mapped[User] = relationship(foreign_keys=[uploaded_by_user_id], viewonly=True)
    approved_by: Mapped[User | None] = relationship(foreign_keys=[approved_by_user_id], viewonly=True)
    rejected_by: Mapped[User | None] = relationship(foreign_keys=[rejected_by_user_id], viewonly=True)


class CorpusPage(UUIDPrimaryKey, Base):
    """The text read from one page of a source document, verbatim.

    `char_start` places the page in the document text (pages joined by a form
    feed), which is what provision spans and chunks are measured against. A
    text-layer page is an exact copy; an OCR page is a machine transcription and
    says so in `method`, `engine` and `confidence`.
    """

    __tablename__ = "corpus_pages"
    __table_args__ = (sa.UniqueConstraint("document_id", "page_number", name="uq_corpus_pages_document_page"),)

    document_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("corpus_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(sa.Integer, nullable=False)  # 1-based
    char_start: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    text: Mapped[str] = mapped_column(sa.Text, nullable=False, default="", server_default="")
    text_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    method: Mapped[str] = mapped_column(sa.String(32), nullable=False)  # pdf_text_layer | ocr | none
    engine: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    confidence: Mapped[float | None] = mapped_column(sa.Float)  # None when the text is exact
    # [{text, bbox: [x0, y0, x1, y1] as page fractions, char_start, char_end, confidence}]
    blocks: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow, server_default=sa.func.now()
    )


class CorpusChunk(UUIDPrimaryKey, Base):
    """A fixed slice of a document's text, for later phases to search.

    Line-bounded, never crossing a page, in document order. `text` equals the
    document text between `char_start` and `char_end`; the pages stay the
    record of the whole text. Nothing searches chunks in Phase 2.
    """

    __tablename__ = "corpus_chunks"
    __table_args__ = (
        sa.UniqueConstraint("document_id", "ordinal", name="uq_corpus_chunks_document_ordinal"),
        sa.ForeignKeyConstraint(
            ["document_id", "lane"], ["corpus_documents.id", "corpus_documents.lane"],
            name="fk_corpus_chunks_document_lane", ondelete="CASCADE",
        ),
        sa.CheckConstraint("char_end > char_start", name="span_not_empty"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False, index=True)
    lane: Mapped[CorpusLane] = _lane()
    ordinal: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    page_number: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    char_start: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow, server_default=sa.func.now()
    )


class Provision(UUIDPrimaryKey, Timestamps, Base):
    """The identity of one provision of one instrument, across its versions.

    `locator` is the label as the source prints it ("3(1)", "Article 15",
    "Schedule I, item 4"); no numbering scheme is assumed. A curator decides
    that two versions are the same provision; nothing infers it.
    """

    __tablename__ = "provisions"
    __table_args__ = (
        sa.UniqueConstraint("id", "lane", name="uq_provisions_id_lane"),
        sa.ForeignKeyConstraint(
            ["instrument_id", "lane"], ["instruments.id", "instruments.lane"], name="fk_provisions_instrument_lane"
        ),
        sa.Index("ix_provisions_instrument_locator", "instrument_id", "locator"),
    )

    instrument_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False, index=True)
    lane: Mapped[CorpusLane] = _lane()
    locator: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    locator_type: Mapped[LocatorType] = mapped_column(enum_column(LocatorType, "locator_type"), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = _user_fk(nullable=False)

    instrument: Mapped[Instrument] = relationship(viewonly=True)


class ProvisionVersion(UUIDPrimaryKey, Timestamps, Base):
    """One version of a provision's text: an exact span of one source document.

    `text` is the document text between `char_start` and `char_end`, copied by
    the server — never typed, never repaired, never paraphrased. `valid_from`
    and `valid_to` (both inclusive, both optional) are when the source says this
    text applies; they are not when it was uploaded, retrieved or approved.
    Once approved, the row never changes again: a correction is a new version.
    """

    __tablename__ = "provision_versions"
    __table_args__ = (
        sa.UniqueConstraint("id", "lane", name="uq_provision_versions_id_lane"),
        sa.UniqueConstraint("provision_id", "version_number", name="uq_provision_versions_number"),
        sa.ForeignKeyConstraint(
            ["provision_id", "lane"], ["provisions.id", "provisions.lane"], name="fk_provision_versions_provision_lane"
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "lane"], ["corpus_documents.id", "corpus_documents.lane"],
            name="fk_provision_versions_document_lane",
        ),
        sa.Index("ix_provision_versions_validity", "valid_from", "valid_to"),
        sa.CheckConstraint("char_end > char_start", name="span_not_empty"),
        sa.CheckConstraint(
            "valid_from IS NULL OR valid_to IS NULL OR valid_to >= valid_from", name="validity_ordered"
        ),
        sa.CheckConstraint(
            "review_state <> 'approved' OR (approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL)",
            name="approval_recorded",
        ),
        sa.CheckConstraint(
            "review_state <> 'rejected' OR (rejected_at IS NOT NULL AND rejected_by_user_id IS NOT NULL)",
            name="rejection_recorded",
        ),
    )

    provision_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False, index=True)
    lane: Mapped[CorpusLane] = _lane()
    document_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    char_start: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    page_start: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    #: Some of the span is machine transcription: approval must acknowledge it.
    ocr_derived: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.false())

    valid_from: Mapped[date | None] = mapped_column(sa.Date)
    valid_to: Mapped[date | None] = mapped_column(sa.Date)

    review_state: Mapped[CorpusReviewState] = _review_state()
    created_by_user_id: Mapped[uuid.UUID] = _user_fk(nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    submitted_by_user_id: Mapped[uuid.UUID | None] = _user_fk()
    approved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    approved_by_user_id: Mapped[uuid.UUID | None] = _user_fk()
    issues_acknowledged: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    rejected_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    rejected_by_user_id: Mapped[uuid.UUID | None] = _user_fk()
    rejection_reason: Mapped[str | None] = mapped_column(sa.String(1000))

    provision: Mapped[Provision] = relationship(viewonly=True)
    document: Mapped[CorpusDocument] = relationship(viewonly=True)
    approved_by: Mapped[User | None] = relationship(foreign_keys=[approved_by_user_id], viewonly=True)
    rejected_by: Mapped[User | None] = relationship(foreign_keys=[rejected_by_user_id], viewonly=True)


class ProvisionStatusEvent(UUIDPrimaryKey, Base):
    """What a cited source says about an approved version, recorded by a curator.

    Append-only: a later event never edits an earlier one, and the history is
    the record. Every event names its basis — an approved source document, a
    reference, or both. It records what the source states; it is not the
    system's conclusion about the law (D-085).
    """

    __tablename__ = "provision_status_events"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["provision_version_id", "lane"], ["provision_versions.id", "provision_versions.lane"],
            name="fk_status_events_version_lane",
        ),
        sa.ForeignKeyConstraint(
            ["basis_document_id", "lane"], ["corpus_documents.id", "corpus_documents.lane"],
            name="fk_status_events_basis_lane",
        ),
        sa.Index("ix_provision_status_events_version_recorded", "provision_version_id", "recorded_at"),
        sa.CheckConstraint("basis_document_id IS NOT NULL OR basis_reference IS NOT NULL", name="basis_required"),
    )

    provision_version_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False)
    lane: Mapped[CorpusLane] = _lane()
    status: Mapped[ProvisionStatus] = mapped_column(enum_column(ProvisionStatus, "provision_status"), nullable=False)
    #: The date the source gives for this status, if it gives one.
    effective_date: Mapped[date | None] = mapped_column(sa.Date)
    basis_document_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid, index=True)
    basis_reference: Mapped[str | None] = mapped_column(sa.String(1000))
    #: The curator's own note. Never statutory text.
    note: Mapped[str | None] = mapped_column(sa.String(2000))
    recorded_by_user_id: Mapped[uuid.UUID] = _user_fk(nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow, server_default=sa.func.now()
    )


# ---------------------------------------------------------------------------
# Immutability, held by the database (D-084)
# ---------------------------------------------------------------------------
#: (table, condition under which any UPDATE is refused; None = always)
IMMUTABLE_ROWS: tuple[tuple[str, str | None], ...] = (
    ("corpus_documents", f"OLD.{_FINAL} OR OLD.lane <> NEW.lane"),
    ("provision_versions", f"OLD.{_FINAL} OR OLD.lane <> NEW.lane"),
    ("instruments", "OLD.lane <> NEW.lane"),
    ("provisions", "OLD.lane <> NEW.lane"),
    ("corpus_pages", None),
    ("corpus_chunks", None),
    ("provision_status_events", None),
)

PG_REFUSE_FUNCTION = """
CREATE OR REPLACE FUNCTION corpus_refuse_update() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'corpus record in % is immutable', TG_TABLE_NAME
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$ LANGUAGE plpgsql
"""


def immutability_ddl(table: str, condition: str | None, dialect: str) -> list[str]:
    """The trigger statements that refuse an UPDATE of `table` (no Python involved)."""
    name = f"trg_{table}_immutable"
    if dialect == "postgresql":
        when = f" WHEN ({condition})" if condition else ""
        return [
            PG_REFUSE_FUNCTION,
            f"CREATE TRIGGER {name} BEFORE UPDATE ON {table} FOR EACH ROW{when} EXECUTE FUNCTION corpus_refuse_update()",
        ]
    if dialect == "sqlite":
        when = f" WHEN {condition}" if condition else ""
        return [
            f"CREATE TRIGGER {name} BEFORE UPDATE ON {table} FOR EACH ROW{when} "
            f"BEGIN SELECT RAISE(ABORT, 'corpus record in {table} is immutable'); END"
        ]
    return []


def _install_triggers(table: sa.Table, condition: str | None) -> None:
    for dialect in ("postgresql", "sqlite"):
        for statement in immutability_ddl(table.name, condition, dialect):
            # sa.DDL formats its statement with %, so a literal % is written %%.
            ddl = sa.DDL(statement.replace("%", "%%"))
            sa.event.listen(table, "after_create", ddl.execute_if(dialect=dialect))


for _table_name, _condition in IMMUTABLE_ROWS:
    _install_triggers(Base.metadata.tables[_table_name], _condition)
