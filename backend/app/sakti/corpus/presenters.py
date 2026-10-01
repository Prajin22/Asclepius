"""Corpus records → API shapes. The storage reference never leaves this module's inputs."""

from sqlalchemy.orm import Session

from app.models import CorpusDocument, CorpusPage, Instrument, Provision, ProvisionStatusEvent, ProvisionVersion, User
from app.sakti.corpus import service
from app.sakti.corpus.authorities import authority
from app.schemas.corpus import (
    ChunkOut,
    DiffBaseline,
    DiffOut,
    InstrumentDetail,
    InstrumentOut,
    InstrumentRef,
    PageOut,
    ProvisionOut,
    ProvisionRef,
    SourceDetail,
    SourceRef,
    SourceSummary,
    SourceText,
    StatusEventOut,
    UserRef,
    VersionDetail,
    VersionSummary,
)


def user_ref(user: User | None) -> UserRef | None:
    return UserRef(id=user.id, email=user.email) if user else None


def instrument_ref(instrument: Instrument) -> InstrumentRef:
    return InstrumentRef(
        id=instrument.id, title=instrument.title, instrument_type=instrument.instrument_type, lane=instrument.lane
    )


def instrument_out(instrument: Instrument) -> InstrumentOut:
    return InstrumentOut.model_validate(instrument, from_attributes=True)


def source_ref(source: CorpusDocument) -> SourceRef:
    return SourceRef(
        id=source.id, title=source.title, source_authority=source.source_authority,
        review_state=source.review_state, sha256=source.sha256,
    )


def source_summary(source: CorpusDocument) -> SourceSummary:
    return SourceSummary(
        id=source.id, lane=source.lane, title=source.title, instrument=instrument_ref(source.instrument),
        source_authority=source.source_authority, authority_name=authority(source.source_authority).name,
        document_type=source.document_type, source_date=source.source_date, retrieved_on=source.retrieved_on,
        terms_status=source.terms_status, ingestion_state=source.ingestion_state,
        ingestion_issues=list(source.ingestion_issues), review_state=source.review_state,
        page_count=source.page_count, sha256=source.sha256, created_at=source.created_at,
        approved_at=source.approved_at,
    )


def _latest_status(db: Session, version: ProvisionVersion):
    events = service.status_events(db, [version.id])
    return events[-1].status if events else None


def version_summary(db: Session, version: ProvisionVersion) -> VersionSummary:
    provision: Provision = version.provision
    return VersionSummary(
        id=version.id, lane=version.lane,
        provision=ProvisionRef(id=provision.id, locator=provision.locator, locator_type=provision.locator_type),
        instrument=instrument_ref(provision.instrument), source_id=version.document_id,
        source_review_state=version.document.review_state,
        version_number=version.version_number, review_state=version.review_state, valid_from=version.valid_from,
        valid_to=version.valid_to, page_start=version.page_start, page_end=version.page_end,
        char_start=version.char_start, char_end=version.char_end, ocr_derived=version.ocr_derived,
        text_sha256=version.text_sha256, created_at=version.created_at, approved_at=version.approved_at,
        latest_status=_latest_status(db, version),
    )


def source_detail(db: Session, source: CorpusDocument) -> SourceDetail:
    summary = source_summary(source)
    return SourceDetail(
        **summary.model_dump(),
        source_url=source.source_url, source_reference=source.source_reference, file_name=source.file_name,
        mime_type=source.mime_type, size_bytes=source.size_bytes,
        text_sha256=source.text_sha256, text_length=source.text_length, parse_error_code=source.parse_error_code,
        extraction_methods=list(source.extraction_methods), extraction_engines=list(source.extraction_engines),
        parsed_at=source.parsed_at, uploaded_by=user_ref(source.uploaded_by), submitted_at=source.submitted_at,
        approved_by=user_ref(source.approved_by), issues_acknowledged=source.issues_acknowledged,
        rejected_at=source.rejected_at, rejected_by=user_ref(source.rejected_by),
        rejection_reason=source.rejection_reason,
        versions=[version_summary(db, v) for v in service.versions_of_source(db, source.id)],
    )


def page_out(page: CorpusPage) -> PageOut:
    return PageOut(
        page_number=page.page_number, char_start=page.char_start, char_end=page.char_start + len(page.text),
        text=page.text, method=page.method, engine=page.engine, confidence=page.confidence,
        warnings=list(page.warnings),
    )


def source_text(db: Session, source: CorpusDocument) -> SourceText:
    document, pages = service.document_text(db, source)
    return SourceText(
        source_id=source.id, text_sha256=source.text_sha256 or "", text_length=len(document),
        pages=[page_out(p) for p in pages],
        chunks=[
            ChunkOut(ordinal=c.ordinal, page_number=c.page_number, char_start=c.char_start, char_end=c.char_end)
            for c in service.chunks_of(db, source.id)
        ],
    )


def provision_out(db: Session, provision: Provision) -> ProvisionOut:
    return ProvisionOut(
        id=provision.id, instrument_id=provision.instrument_id, lane=provision.lane, locator=provision.locator,
        locator_type=provision.locator_type, created_at=provision.created_at,
        versions=[version_summary(db, v) for v in service.versions_of_provision(db, provision.id)],
    )


def instrument_detail(db: Session, instrument: Instrument) -> InstrumentDetail:
    return InstrumentDetail(
        **instrument_out(instrument).model_dump(),
        provisions=[provision_out(db, p) for p in service.provisions_of(db, instrument.id)],
        sources=[source_summary(s) for s in service.sources_of(db, instrument.id)],
    )


def status_event_out(db: Session, event: ProvisionStatusEvent) -> StatusEventOut:
    basis = db.get(CorpusDocument, event.basis_document_id) if event.basis_document_id else None
    return StatusEventOut(
        id=event.id, status=event.status, effective_date=event.effective_date,
        basis_source=source_ref(basis) if basis else None, basis_reference=event.basis_reference, note=event.note,
        recorded_by=user_ref(db.get(User, event.recorded_by_user_id)), recorded_at=event.recorded_at,
    )


def version_detail(db: Session, version: ProvisionVersion) -> VersionDetail:
    return VersionDetail(
        **version_summary(db, version).model_dump(),
        text=version.text, source=source_ref(version.document), issues_acknowledged=version.issues_acknowledged,
        approved_by=user_ref(version.approved_by), rejected_at=version.rejected_at,
        rejected_by=user_ref(version.rejected_by), rejection_reason=version.rejection_reason,
        status_events=[status_event_out(db, e) for e in service.status_events(db, [version.id])],
    )


def source_diff_out(baseline: CorpusDocument | None, diff: dict) -> DiffOut:
    return DiffOut(
        baseline=DiffBaseline(kind="source", id=baseline.id, label=baseline.title, approved_at=baseline.approved_at)
        if baseline else None,
        **diff,
    )


def version_diff_out(baseline: ProvisionVersion | None, diff: dict) -> DiffOut:
    return DiffOut(
        baseline=DiffBaseline(
            kind="version", id=baseline.id, label=f"v{baseline.version_number}", approved_at=baseline.approved_at
        ) if baseline else None,
        **diff,
    )
