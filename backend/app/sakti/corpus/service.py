"""The curator workflow over the legal source corpus (Phase 2, D-081–D-086).

    create instrument → upload source (file + where it came from) → parse
    → mark provision versions as exact spans of the parsed text
    → submit → approve | reject           (sources and versions alike)
    → record status events on approved versions, citing their basis

Every step is explicit; nothing is approved because something else happened.
Every change is audited in the same transaction as the change. Approved and
rejected records are final: an attempt to change one is refused, and the
refusal is audited too.

Rules that hold throughout:

* a record's lane is given once and never changes, and a record only ever
  joins records of the same lane (the database enforces it as well);
* provision text is cut from the stored document text by the server, from
  offsets — a curator never types it and nothing rewrites it;
* a version can only be approved after its source document is, and an approval
  names the checksum the curator reviewed, so nothing else gets approved.
"""

import hashlib
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    CorpusChunk,
    CorpusDocument,
    CorpusPage,
    Instrument,
    Provision,
    ProvisionStatusEvent,
    ProvisionVersion,
    User,
)
from app.models.enums import (
    CorpusDocumentType,
    CorpusLane,
    CorpusReviewState,
    IngestionState,
    InstrumentType,
    LocatorType,
    ProvisionStatus,
    SourceAuthority,
)
from app.providers.documents import METHOD_OCR, PDF_MIME
from app.providers.storage import get_storage
from app.sakti.corpus import diff as corpus_diff
from app.sakti.corpus import ingest, text
from app.sakti.corpus.authorities import authority
from app.services import audit
from app.services.audit import RequestContext
from app.services.errors import Conflict, DocumentIntegrityError, InvalidInput, InvalidTransition, NotFound

READ_STATES = (IngestionState.PARSED, IngestionState.NEEDS_REVIEW)
FINAL_STATES = (CorpusReviewState.APPROVED, CorpusReviewState.REJECTED)

#: The whole state machine: action → (states it may start from, state it ends in).
TRANSITIONS: dict[str, tuple[frozenset[CorpusReviewState], CorpusReviewState]] = {
    "submit": (frozenset({CorpusReviewState.DRAFT}), CorpusReviewState.UNDER_REVIEW),
    "approve": (frozenset({CorpusReviewState.UNDER_REVIEW}), CorpusReviewState.APPROVED),
    "reject": (frozenset({CorpusReviewState.UNDER_REVIEW}), CorpusReviewState.REJECTED),
}


def _now() -> datetime:
    return datetime.now(UTC)


def _today() -> date:
    return _now().date()


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


def _refuse_final(
    db: Session, actor: User, record: CorpusDocument | ProvisionVersion, action: str, ctx: RequestContext | None
) -> None:
    """An approved or rejected record is never changed. Say so, and keep a record of the attempt."""
    if record.review_state not in FINAL_STATES:
        return
    kind = "corpus_source" if isinstance(record, CorpusDocument) else "provision_version"
    audit.record(
        db, actor=actor, action="corpus.mutation_refused", resource_type=kind, resource_id=record.id,
        details={"attempted": action, "review_state": record.review_state.value}, ctx=ctx,
    )
    db.commit()
    raise Conflict(
        f"This {kind.replace('_', ' ')} is {record.review_state.value} and cannot be changed. "
        "A correction is a new version.",
        code="corpus_record_final",
    )


def _transition(
    db: Session, actor: User, record: CorpusDocument | ProvisionVersion, action: str, ctx: RequestContext | None
) -> CorpusReviewState:
    allowed, target = TRANSITIONS[action]
    if record.review_state not in allowed:
        _refuse_final(db, actor, record, action, ctx)
        raise InvalidTransition(
            f"Cannot {action} from {record.review_state.value}", code="invalid_transition"
        )
    return target


def _require_second_person(actor: User, *people: uuid.UUID | None) -> None:
    """With CORPUS_SEPARATE_APPROVER, nobody approves what they uploaded, cut or submitted."""
    if get_settings().corpus_separate_approver and actor.id in {p for p in people if p}:
        raise Conflict("A different curator must approve this", code="approver_must_differ")


def _lane_mismatch(what: str) -> InvalidInput:
    return InvalidInput(f"{what} belongs to the other lane. Records never cross lanes.", code="lane_mismatch")


def _validity(valid_from: date | None, valid_to: date | None) -> None:
    if valid_from and valid_to and valid_to < valid_from:
        raise InvalidInput("The validity end date is before its start date", code="validity_not_ordered")


# ---------------------------------------------------------------------------
# Instruments and provisions
# ---------------------------------------------------------------------------


def list_instruments(db: Session, lane: CorpusLane | None = None) -> list[Instrument]:
    q = select(Instrument).order_by(Instrument.lane, Instrument.title)
    if lane:
        q = q.where(Instrument.lane == lane)
    return list(db.scalars(q))


def get_instrument(db: Session, instrument_id: uuid.UUID) -> Instrument:
    instrument = db.get(Instrument, instrument_id)
    if instrument is None:
        raise NotFound("Instrument not found")
    return instrument


def create_instrument(
    db: Session, actor: User, *, lane: CorpusLane, instrument_type: InstrumentType, title: str, issued_by: str,
    description: str | None, ctx: RequestContext | None = None,
) -> Instrument:
    exists = db.scalar(
        select(Instrument.id).where(
            Instrument.lane == lane, Instrument.instrument_type == instrument_type, Instrument.title == title
        )
    )
    if exists:
        raise Conflict("An instrument with this title and type already exists in this lane", code="instrument_exists")
    instrument = Instrument(
        lane=lane, instrument_type=instrument_type, title=title, issued_by=issued_by,
        description=description or None, created_by_user_id=actor.id,
    )
    db.add(instrument)
    db.flush()
    audit.record(
        db, actor=actor, action="corpus.instrument_created", resource_type="instrument", resource_id=instrument.id,
        details={"lane": lane.value, "instrument_type": instrument_type.value}, ctx=ctx,
    )
    db.commit()
    return instrument


def provisions_of(db: Session, instrument_id: uuid.UUID) -> list[Provision]:
    return list(
        db.scalars(select(Provision).where(Provision.instrument_id == instrument_id).order_by(Provision.created_at))
    )


def get_provision(db: Session, provision_id: uuid.UUID) -> Provision:
    provision = db.get(Provision, provision_id)
    if provision is None:
        raise NotFound("Provision not found")
    return provision


def create_provision(
    db: Session, actor: User, instrument_id: uuid.UUID, *, locator: str, locator_type: LocatorType,
    ctx: RequestContext | None = None,
) -> Provision:
    """A new provision identity. Its lane is the instrument's, copied here and held by the database."""
    instrument = get_instrument(db, instrument_id)
    provision = Provision(
        instrument_id=instrument.id, lane=instrument.lane, locator=locator, locator_type=locator_type,
        created_by_user_id=actor.id,
    )
    db.add(provision)
    db.flush()
    audit.record(
        db, actor=actor, action="corpus.provision_created", resource_type="provision", resource_id=provision.id,
        details={"lane": instrument.lane.value, "instrument_id": str(instrument.id),
                 "locator_type": locator_type.value},
        ctx=ctx,
    )
    db.commit()
    return provision


# ---------------------------------------------------------------------------
# Source documents
# ---------------------------------------------------------------------------


def list_sources(
    db: Session, lane: CorpusLane | None = None, review_state: CorpusReviewState | None = None
) -> list[CorpusDocument]:
    q = select(CorpusDocument).order_by(CorpusDocument.created_at.desc())
    if lane:
        q = q.where(CorpusDocument.lane == lane)
    if review_state:
        q = q.where(CorpusDocument.review_state == review_state)
    return list(db.scalars(q))


def get_source(db: Session, source_id: uuid.UUID, *, for_update: bool = False) -> CorpusDocument:
    q = select(CorpusDocument).where(CorpusDocument.id == source_id)
    source = db.scalar(q.with_for_update() if for_update else q)
    if source is None:
        raise NotFound("Source document not found")
    return source


def sources_of(db: Session, instrument_id: uuid.UUID) -> list[CorpusDocument]:
    return list(
        db.scalars(
            select(CorpusDocument)
            .where(CorpusDocument.instrument_id == instrument_id)
            .order_by(CorpusDocument.created_at)
        )
    )


@dataclass(frozen=True)
class SourceMetadata:
    lane: CorpusLane
    instrument_id: uuid.UUID
    title: str
    source_authority: SourceAuthority
    document_type: CorpusDocumentType
    retrieved_on: date
    source_url: str | None = None
    source_reference: str | None = None
    source_date: date | None = None


def upload_source(
    db: Session, actor: User, meta: SourceMetadata, *, filename: str | None, declared_mime: str | None, data: bytes,
    ctx: RequestContext | None = None,
) -> CorpusDocument:
    """Store an official source file with its provenance. It is a draft, and unread."""
    settings = get_settings()
    display_name = ingest.validate_source_file(filename, declared_mime, data, settings.corpus_max_upload_bytes)

    instrument = get_instrument(db, meta.instrument_id)
    if instrument.lane != meta.lane:
        raise _lane_mismatch("The instrument")
    if authority(meta.source_authority).lane != meta.lane:
        raise InvalidInput("That source authority does not publish for this lane", code="authority_not_in_lane")
    source_url = ingest.validate_source_url(meta.source_url)
    source_reference = (meta.source_reference or "").strip() or None
    if source_url is None and source_reference is None:
        raise InvalidInput("Say where the file came from: a URL, a reference, or both", code="provenance_required")
    latest = _today() + timedelta(days=1)  # a curator a timezone ahead of UTC
    if meta.retrieved_on > latest:
        raise InvalidInput("The retrieval date is in the future", code="date_in_future")
    if meta.source_date and meta.source_date > latest:
        raise InvalidInput("The source date is in the future", code="date_in_future")

    sha256 = hashlib.sha256(data).hexdigest()
    duplicate = db.scalar(
        select(CorpusDocument.id).where(
            CorpusDocument.sha256 == sha256, CorpusDocument.review_state != CorpusReviewState.REJECTED
        )
    )
    if duplicate:
        raise Conflict("This exact file is already in the corpus", code="duplicate_source")

    document_id = uuid.uuid4()
    reference = ingest.store_source(document_id, data)
    source = CorpusDocument(
        id=document_id, lane=meta.lane, instrument_id=instrument.id, title=meta.title,
        source_authority=meta.source_authority, document_type=meta.document_type, source_url=source_url,
        source_reference=source_reference, source_date=meta.source_date, retrieved_on=meta.retrieved_on,
        file_name=display_name, mime_type=PDF_MIME, size_bytes=len(data), sha256=sha256,
        storage_reference=reference, uploaded_by_user_id=actor.id,
    )
    db.add(source)
    audit.record(
        db, actor=actor, action="corpus.source_uploaded", resource_type="corpus_source", resource_id=document_id,
        details={"lane": meta.lane.value, "source_authority": meta.source_authority.value,
                 "document_type": meta.document_type.value, "instrument_id": str(instrument.id),
                 "sha256": sha256, "size_bytes": len(data)},
        ctx=ctx,
    )
    try:
        db.commit()
    except Exception:
        get_storage().delete(reference)  # no orphaned files
        raise
    return source


def parse_source(db: Session, actor: User, source_id: uuid.UUID, ctx: RequestContext | None = None) -> CorpusDocument:
    """Read the stored file into pages and chunks. Once read, a source is never read again."""
    source = get_source(db, source_id, for_update=True)
    _refuse_final(db, actor, source, "parse", ctx)
    if source.ingestion_state not in (IngestionState.UPLOADED, IngestionState.FAILED):
        raise Conflict("This source has already been read", code="already_parsed")

    data = ingest.load_original(source)  # integrity before anything else
    reading = ingest.read_source(data, get_settings())
    source.parsed_at, source.parsed_by_user_id = _now(), actor.id
    source.page_count = reading.page_count or None
    if reading.failed:
        source.ingestion_state = IngestionState.FAILED
        source.parse_error_code = reading.error_code
        audit.record(
            db, actor=actor, action="corpus.source_parse_failed", resource_type="corpus_source",
            resource_id=source.id, details={"error": reading.error_code, "pages": reading.page_count}, ctx=ctx,
        )
        db.commit()
        return source

    page_texts = [page.text for page in reading.pages]
    document_text, starts = text.assemble(page_texts)
    for page, start in zip(reading.pages, starts, strict=True):
        db.add(
            CorpusPage(
                document_id=source.id, page_number=page.page_number, char_start=start, text=page.text,
                text_sha256=text.sha256_text(page.text), method=page.method, engine=page.engine[:160],
                confidence=page.confidence, blocks=[block.as_dict() for block in page.blocks],
                warnings=list(page.warnings),
            )
        )
    chunks = text.chunk_pages([(p.page_number, s, p.text) for p, s in zip(reading.pages, starts, strict=True)])
    for chunk in chunks:
        chunk_text = document_text[chunk.char_start:chunk.char_end]
        db.add(
            CorpusChunk(
                document_id=source.id, lane=source.lane, ordinal=chunk.ordinal, page_number=chunk.page_number,
                char_start=chunk.char_start, char_end=chunk.char_end, text=chunk_text,
                text_sha256=text.sha256_text(chunk_text),
            )
        )
    source.ingestion_state = IngestionState.NEEDS_REVIEW if reading.issues else IngestionState.PARSED
    source.ingestion_issues = reading.issues
    source.parse_error_code = None
    source.text_sha256 = text.sha256_text(document_text)
    source.text_length = len(document_text)
    source.extraction_methods = sorted({page.method for page in reading.pages})
    source.extraction_engines = sorted({page.engine for page in reading.pages})
    audit.record(
        db, actor=actor, action="corpus.source_parsed", resource_type="corpus_source", resource_id=source.id,
        details={"pages": reading.page_count, "chunks": len(chunks), "methods": source.extraction_methods,
                 "issues": reading.issues, "text_sha256": source.text_sha256},
        ctx=ctx,
    )
    db.commit()
    return source


def pages_of(db: Session, source_id: uuid.UUID) -> list[CorpusPage]:
    return list(
        db.scalars(select(CorpusPage).where(CorpusPage.document_id == source_id).order_by(CorpusPage.page_number))
    )


def chunks_of(db: Session, source_id: uuid.UUID) -> list[CorpusChunk]:
    return list(
        db.scalars(select(CorpusChunk).where(CorpusChunk.document_id == source_id).order_by(CorpusChunk.ordinal))
    )


def document_text(db: Session, source: CorpusDocument) -> tuple[str, list[CorpusPage]]:
    """The stored document text, rebuilt from its pages and checked against the hash taken when it was read."""
    pages = pages_of(db, source.id)
    assembled, _ = text.assemble([page.text for page in pages])
    for page in pages:
        if text.sha256_text(page.text) != page.text_sha256:
            raise DocumentIntegrityError("A stored page no longer matches the text that was read")
    if source.text_sha256 is not None and text.sha256_text(assembled) != source.text_sha256:
        raise DocumentIntegrityError("The stored text no longer matches the text that was read")
    return assembled, pages


def submit_source(db: Session, actor: User, source_id: uuid.UUID, ctx: RequestContext | None = None) -> CorpusDocument:
    source = get_source(db, source_id, for_update=True)
    target = _transition(db, actor, source, "submit", ctx)
    if source.ingestion_state not in READ_STATES:
        raise Conflict("Only a source whose text has been read can be reviewed", code="source_not_read")
    source.review_state, source.submitted_at, source.submitted_by_user_id = target, _now(), actor.id
    audit.record(
        db, actor=actor, action="corpus.source_submitted", resource_type="corpus_source", resource_id=source.id,
        details={"ingestion_state": source.ingestion_state.value}, ctx=ctx,
    )
    db.commit()
    return source


def approve_source(
    db: Session, actor: User, source_id: uuid.UUID, *, expected_sha256: str, acknowledge_issues: bool,
    ctx: RequestContext | None = None,
) -> CorpusDocument:
    """Accept a source as an authentic copy of what it says it is. The file and its text are re-verified first."""
    source = get_source(db, source_id, for_update=True)
    target = _transition(db, actor, source, "approve", ctx)
    _require_second_person(actor, source.uploaded_by_user_id, source.submitted_by_user_id)
    if expected_sha256 != source.sha256:
        raise Conflict("The file reviewed is not the file stored", code="checksum_mismatch")
    if source.ingestion_state == IngestionState.NEEDS_REVIEW and not acknowledge_issues:
        raise InvalidInput(
            "Some of this text is machine transcription or missing: confirm it was checked against the original",
            code="issues_not_acknowledged",
        )
    ingest.load_original(source)
    document_text(db, source)
    source.review_state, source.approved_at, source.approved_by_user_id = target, _now(), actor.id
    source.issues_acknowledged = bool(source.ingestion_issues) and acknowledge_issues
    audit.record(
        db, actor=actor, action="corpus.source_approved", resource_type="corpus_source", resource_id=source.id,
        details={"lane": source.lane.value, "source_authority": source.source_authority.value,
                 "instrument_id": str(source.instrument_id), "sha256": source.sha256,
                 "text_sha256": source.text_sha256, "page_count": source.page_count,
                 "methods": source.extraction_methods, "issues": source.ingestion_issues,
                 "issues_acknowledged": source.issues_acknowledged},
        ctx=ctx,
    )
    db.commit()
    return source


def reject_source(
    db: Session, actor: User, source_id: uuid.UUID, *, reason: str, ctx: RequestContext | None = None
) -> CorpusDocument:
    """Reject a source. Versions cut from it that are not yet decided are rejected with it."""
    source = get_source(db, source_id, for_update=True)
    target = _transition(db, actor, source, "reject", ctx)
    now = _now()
    source.review_state, source.rejected_at, source.rejected_by_user_id = target, now, actor.id
    source.rejection_reason = reason
    pending = list(
        db.scalars(
            select(ProvisionVersion).where(
                ProvisionVersion.document_id == source.id,
                ProvisionVersion.review_state.in_((CorpusReviewState.DRAFT, CorpusReviewState.UNDER_REVIEW)),
            )
        )
    )
    for version in pending:
        version.review_state, version.rejected_at, version.rejected_by_user_id = target, now, actor.id
        version.rejection_reason = "Its source document was rejected."
    audit.record(
        db, actor=actor, action="corpus.source_rejected", resource_type="corpus_source", resource_id=source.id,
        details={"versions_rejected": [str(v.id) for v in pending]}, ctx=ctx,
    )
    db.commit()
    return source


def source_baseline(db: Session, source: CorpusDocument) -> CorpusDocument | None:
    """The most recently approved other source of the same instrument, to compare against."""
    return db.scalar(
        select(CorpusDocument)
        .where(
            CorpusDocument.instrument_id == source.instrument_id,
            CorpusDocument.id != source.id,
            CorpusDocument.review_state == CorpusReviewState.APPROVED,
        )
        .order_by(CorpusDocument.approved_at.desc())
        .limit(1)
    )


def source_diff(db: Session, source: CorpusDocument) -> tuple[CorpusDocument | None, dict]:
    if source.ingestion_state not in READ_STATES:
        raise Conflict("This source has not been read yet", code="source_not_read")
    new, _ = document_text(db, source)
    baseline = source_baseline(db, source)
    old = document_text(db, baseline)[0] if baseline else ""
    return baseline, corpus_diff.diff_texts(old, new)


# ---------------------------------------------------------------------------
# Provision versions
# ---------------------------------------------------------------------------


def get_version(db: Session, version_id: uuid.UUID, *, for_update: bool = False) -> ProvisionVersion:
    q = select(ProvisionVersion).where(ProvisionVersion.id == version_id)
    version = db.scalar(q.with_for_update() if for_update else q)
    if version is None:
        raise NotFound("Provision version not found")
    return version


def versions_of_provision(db: Session, provision_id: uuid.UUID) -> list[ProvisionVersion]:
    return list(
        db.scalars(
            select(ProvisionVersion)
            .where(ProvisionVersion.provision_id == provision_id)
            .order_by(ProvisionVersion.version_number)
        )
    )


def versions_of_source(db: Session, source_id: uuid.UUID) -> list[ProvisionVersion]:
    return list(
        db.scalars(
            select(ProvisionVersion)
            .where(ProvisionVersion.document_id == source_id)
            .order_by(ProvisionVersion.char_start, ProvisionVersion.created_at)
        )
    )


def _cut(db: Session, source: CorpusDocument, char_start: int, char_end: int) -> tuple[str, int, int, bool]:
    """The exact text of a span, the pages it covers, and whether any of it is OCR."""
    document, pages = document_text(db, source)
    if not 0 <= char_start < char_end <= len(document):
        raise InvalidInput("The span is outside the document text", code="span_out_of_range")
    span = document[char_start:char_end]
    if not span.strip():
        raise InvalidInput("The span contains no text", code="span_empty")
    first, last = text.pages_of_span(
        [p.char_start for p in pages], [len(p.text) for p in pages], char_start, char_end
    )
    ocr = any(p.method == METHOD_OCR for p in pages[first - 1:last])
    return span, first, last, ocr


def create_version(
    db: Session, actor: User, source_id: uuid.UUID, *, provision_id: uuid.UUID, char_start: int, char_end: int,
    valid_from: date | None, valid_to: date | None, ctx: RequestContext | None = None,
) -> ProvisionVersion:
    """A new version of a provision: the exact text of a span of a read source. Always a draft."""
    source = get_source(db, source_id)
    if source.review_state == CorpusReviewState.REJECTED:
        raise Conflict("This source was rejected", code="source_rejected")
    if source.ingestion_state not in READ_STATES:
        raise Conflict("This source has not been read yet", code="source_not_read")
    provision = get_provision(db, provision_id)
    if provision.lane != source.lane:
        raise _lane_mismatch("The provision")
    _validity(valid_from, valid_to)
    span, first, last, ocr = _cut(db, source, char_start, char_end)

    number = (
        db.scalar(select(func.max(ProvisionVersion.version_number)).where(ProvisionVersion.provision_id == provision.id))
        or 0
    ) + 1
    version = ProvisionVersion(
        provision_id=provision.id, lane=provision.lane, document_id=source.id, version_number=number, text=span,
        text_sha256=text.sha256_text(span), char_start=char_start, char_end=char_end, page_start=first,
        page_end=last, ocr_derived=ocr, valid_from=valid_from, valid_to=valid_to, created_by_user_id=actor.id,
    )
    db.add(version)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Conflict("Another version of this provision was created at the same time; try again",
                       code="version_conflict") from None
    audit.record(
        db, actor=actor, action="corpus.version_created", resource_type="provision_version", resource_id=version.id,
        details={"lane": version.lane.value, "provision_id": str(provision.id), "source_id": str(source.id),
                 "version_number": number, "text_sha256": version.text_sha256, "ocr_derived": ocr},
        ctx=ctx,
    )
    db.commit()
    return version


_UNSET = object()


def update_version(
    db: Session, actor: User, version_id: uuid.UUID, *, char_start: int | None = None, char_end: int | None = None,
    valid_from: date | None | object = _UNSET, valid_to: date | None | object = _UNSET,
    ctx: RequestContext | None = None,
) -> ProvisionVersion:
    """Adjust a draft: its span or its dates. Anything submitted or decided is not edited."""
    version = get_version(db, version_id, for_update=True)
    _refuse_final(db, actor, version, "update", ctx)
    if version.review_state != CorpusReviewState.DRAFT:
        raise InvalidTransition("Only a draft can be changed", code="version_not_editable")
    new_from = version.valid_from if valid_from is _UNSET else valid_from
    new_to = version.valid_to if valid_to is _UNSET else valid_to
    _validity(new_from, new_to)  # type: ignore[arg-type]
    start = version.char_start if char_start is None else char_start
    end = version.char_end if char_end is None else char_end
    changed: list[str] = []
    if (start, end) != (version.char_start, version.char_end):
        span, first, last, ocr = _cut(db, get_source(db, version.document_id), start, end)
        version.char_start, version.char_end, version.text = start, end, span
        version.text_sha256, version.page_start, version.page_end, version.ocr_derived = (
            text.sha256_text(span), first, last, ocr,
        )
        changed.append("span")
    if (new_from, new_to) != (version.valid_from, version.valid_to):
        version.valid_from, version.valid_to = new_from, new_to  # type: ignore[assignment]
        changed.append("validity")
    if changed:
        audit.record(
            db, actor=actor, action="corpus.version_updated", resource_type="provision_version",
            resource_id=version.id, details={"changed": changed, "text_sha256": version.text_sha256}, ctx=ctx,
        )
    db.commit()
    return version


def submit_version(db: Session, actor: User, version_id: uuid.UUID, ctx: RequestContext | None = None) -> ProvisionVersion:
    version = get_version(db, version_id, for_update=True)
    target = _transition(db, actor, version, "submit", ctx)
    version.review_state, version.submitted_at, version.submitted_by_user_id = target, _now(), actor.id
    audit.record(
        db, actor=actor, action="corpus.version_submitted", resource_type="provision_version",
        resource_id=version.id, details={"text_sha256": version.text_sha256}, ctx=ctx,
    )
    db.commit()
    return version


def approve_version(
    db: Session, actor: User, version_id: uuid.UUID, *, expected_text_sha256: str, acknowledge_issues: bool,
    ctx: RequestContext | None = None,
) -> ProvisionVersion:
    """Accept a version's text as the provision's text. Its source must already be approved."""
    version = get_version(db, version_id, for_update=True)
    target = _transition(db, actor, version, "approve", ctx)
    source = get_source(db, version.document_id)
    if source.review_state != CorpusReviewState.APPROVED:
        raise Conflict("Approve the source document before any text cut from it", code="source_not_approved")
    _require_second_person(actor, version.created_by_user_id, version.submitted_by_user_id)
    if expected_text_sha256 != version.text_sha256:
        raise Conflict("The text reviewed is not the text stored", code="checksum_mismatch")
    if version.ocr_derived and not acknowledge_issues:
        raise InvalidInput(
            "This text is machine transcription: confirm it was checked against the original",
            code="issues_not_acknowledged",
        )
    document, _ = document_text(db, source)
    exact = document[version.char_start:version.char_end]
    if exact != version.text or text.sha256_text(exact) != version.text_sha256:
        raise DocumentIntegrityError("The version's text no longer matches its source")
    version.review_state, version.approved_at, version.approved_by_user_id = target, _now(), actor.id
    version.issues_acknowledged = version.ocr_derived and acknowledge_issues
    provision = get_provision(db, version.provision_id)
    audit.record(
        db, actor=actor, action="corpus.version_approved", resource_type="provision_version",
        resource_id=version.id,
        details={"lane": version.lane.value, "provision_id": str(version.provision_id),
                 "instrument_id": str(provision.instrument_id), "version_number": version.version_number,
                 "source_id": str(source.id), "source_sha256": source.sha256, "text_sha256": version.text_sha256,
                 "valid_from": version.valid_from.isoformat() if version.valid_from else None,
                 "valid_to": version.valid_to.isoformat() if version.valid_to else None,
                 "ocr_derived": version.ocr_derived, "issues_acknowledged": version.issues_acknowledged},
        ctx=ctx,
    )
    db.commit()
    return version


def reject_version(
    db: Session, actor: User, version_id: uuid.UUID, *, reason: str, ctx: RequestContext | None = None
) -> ProvisionVersion:
    version = get_version(db, version_id, for_update=True)
    target = _transition(db, actor, version, "reject", ctx)
    version.review_state, version.rejected_at, version.rejected_by_user_id = target, _now(), actor.id
    version.rejection_reason = reason
    audit.record(
        db, actor=actor, action="corpus.version_rejected", resource_type="provision_version",
        resource_id=version.id, details={"text_sha256": version.text_sha256}, ctx=ctx,
    )
    db.commit()
    return version


def version_baseline(db: Session, version: ProvisionVersion) -> ProvisionVersion | None:
    """The most recently approved other version of the same provision."""
    return db.scalar(
        select(ProvisionVersion)
        .where(
            ProvisionVersion.provision_id == version.provision_id,
            ProvisionVersion.id != version.id,
            ProvisionVersion.review_state == CorpusReviewState.APPROVED,
        )
        .order_by(ProvisionVersion.approved_at.desc())
        .limit(1)
    )


def version_diff(db: Session, version: ProvisionVersion) -> tuple[ProvisionVersion | None, dict]:
    baseline = version_baseline(db, version)
    return baseline, corpus_diff.diff_texts(baseline.text if baseline else "", version.text)


# ---------------------------------------------------------------------------
# Status history
# ---------------------------------------------------------------------------


def status_events(db: Session, version_ids: Iterable[uuid.UUID]) -> list[ProvisionStatusEvent]:
    ids = list(version_ids)
    if not ids:
        return []
    return list(
        db.scalars(
            select(ProvisionStatusEvent)
            .where(ProvisionStatusEvent.provision_version_id.in_(ids))
            .order_by(ProvisionStatusEvent.recorded_at, ProvisionStatusEvent.id)
        )
    )


def record_status(
    db: Session, actor: User, version_id: uuid.UUID, *, status: ProvisionStatus, effective_date: date | None,
    basis_source_id: uuid.UUID | None, basis_reference: str | None, note: str | None,
    ctx: RequestContext | None = None,
) -> ProvisionStatusEvent:
    """Append what a cited source says about an approved version. Earlier events are never changed."""
    version = get_version(db, version_id)
    if version.review_state != CorpusReviewState.APPROVED:
        raise Conflict("Status is recorded only for approved text", code="version_not_approved")
    basis_reference = (basis_reference or "").strip() or None
    if basis_source_id is not None:
        basis = get_source(db, basis_source_id)
        if basis.lane != version.lane:
            raise _lane_mismatch("The basis document")
        if basis.review_state != CorpusReviewState.APPROVED:
            raise Conflict("A status must rest on an approved source", code="basis_not_approved")
    elif basis_reference is None:
        raise InvalidInput("Cite the basis for this status: an approved source, a reference, or both",
                           code="basis_required")
    event = ProvisionStatusEvent(
        provision_version_id=version.id, lane=version.lane, status=status, effective_date=effective_date,
        basis_document_id=basis_source_id, basis_reference=basis_reference, note=(note or "").strip() or None,
        recorded_by_user_id=actor.id,
    )
    db.add(event)
    db.flush()
    audit.record(
        db, actor=actor, action="corpus.status_recorded", resource_type="provision_version", resource_id=version.id,
        details={"event_id": str(event.id), "status": status.value,
                 "effective_date": effective_date.isoformat() if effective_date else None,
                 "basis_source_id": str(basis_source_id) if basis_source_id else None},
        ctx=ctx,
    )
    db.commit()
    return event


# ---------------------------------------------------------------------------
# Review queue
# ---------------------------------------------------------------------------


def review_queue(db: Session) -> tuple[list[CorpusDocument], list[ProvisionVersion]]:
    sources = list(
        db.scalars(
            select(CorpusDocument)
            .where(CorpusDocument.review_state == CorpusReviewState.UNDER_REVIEW)
            .order_by(CorpusDocument.submitted_at)
        )
    )
    versions = list(
        db.scalars(
            select(ProvisionVersion)
            .where(ProvisionVersion.review_state == CorpusReviewState.UNDER_REVIEW)
            .order_by(ProvisionVersion.submitted_at)
        )
    )
    return sources, versions


def drafts(db: Session) -> tuple[list[CorpusDocument], list[ProvisionVersion]]:
    sources = list(
        db.scalars(
            select(CorpusDocument)
            .where(CorpusDocument.review_state == CorpusReviewState.DRAFT)
            .order_by(CorpusDocument.created_at.desc())
        )
    )
    versions = list(
        db.scalars(
            select(ProvisionVersion)
            .where(ProvisionVersion.review_state == CorpusReviewState.DRAFT)
            .order_by(ProvisionVersion.created_at.desc())
        )
    )
    return sources, versions
