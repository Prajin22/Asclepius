"""The legal source corpus: curator ingestion and approval (IP-SAKTI Phase 2).

Mounted only when PRODUCT=ip_sakti. Every change requires the curator role;
an administrator may read, for oversight, and change nothing. Users and
facilitators have no access at all: nothing here answers a question, searches
the corpus or serves legal text to the public — those are later phases, and
they will read approved records only.
"""

import uuid
from datetime import date
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.api.deps import DB, Ctx, require_roles
from app.core.config import get_settings
from app.models import User
from app.models.enums import (
    CorpusDocumentType,
    CorpusLane,
    CorpusReviewState,
    SourceAuthority,
    UserRole,
)
from app.sakti.corpus import ingest, presenters, service
from app.sakti.corpus.authorities import AUTHORITIES
from app.schemas.corpus import (
    ApproveSource,
    ApproveVersion,
    AuthorityOut,
    DiffOut,
    InstrumentCreate,
    InstrumentDetail,
    InstrumentOut,
    ProvisionCreate,
    ProvisionOut,
    Reject,
    ReviewQueue,
    SourceDetail,
    SourceSummary,
    SourceText,
    StatusEventCreate,
    StatusEventOut,
    VersionCreate,
    VersionDetail,
    VersionSummary,
    VersionUpdate,
)
from app.services.errors import Conflict

router = APIRouter(prefix="/corpus", tags=["corpus"])

Curator = Annotated[User, Depends(require_roles(UserRole.CURATOR))]
Reader = Annotated[User, Depends(require_roles(UserRole.CURATOR, UserRole.ADMIN))]


# ---------- reference data ----------


@router.get("/authorities", response_model=list[AuthorityOut])
def list_authorities(_: Reader) -> list[AuthorityOut]:
    """The official sources a file may come from. Reuse terms: unknown for every one."""
    return [AuthorityOut(code=a.code, name=a.name, lane=a.lane, terms_status=a.terms_status) for a in AUTHORITIES.values()]


# ---------- instruments and provisions ----------


@router.get("/instruments", response_model=list[InstrumentOut])
def list_instruments(_: Reader, db: DB, lane: CorpusLane | None = None) -> list[InstrumentOut]:
    return [presenters.instrument_out(i) for i in service.list_instruments(db, lane)]


@router.post("/instruments", response_model=InstrumentOut, status_code=status.HTTP_201_CREATED)
def create_instrument(data: InstrumentCreate, curator: Curator, db: DB, ctx: Ctx) -> InstrumentOut:
    instrument = service.create_instrument(
        db, curator, lane=data.lane, instrument_type=data.instrument_type, title=data.title,
        issued_by=data.issued_by, description=data.description, ctx=ctx,
    )
    return presenters.instrument_out(instrument)


@router.get("/instruments/{instrument_id}", response_model=InstrumentDetail)
def get_instrument(instrument_id: uuid.UUID, _: Reader, db: DB) -> InstrumentDetail:
    return presenters.instrument_detail(db, service.get_instrument(db, instrument_id))


@router.post(
    "/instruments/{instrument_id}/provisions", response_model=ProvisionOut, status_code=status.HTTP_201_CREATED
)
def create_provision(
    instrument_id: uuid.UUID, data: ProvisionCreate, curator: Curator, db: DB, ctx: Ctx
) -> ProvisionOut:
    provision = service.create_provision(
        db, curator, instrument_id, locator=data.locator, locator_type=data.locator_type, ctx=ctx
    )
    return presenters.provision_out(db, provision)


# ---------- source documents ----------


@router.get("/sources", response_model=list[SourceSummary])
def list_sources(
    _: Reader, db: DB, lane: CorpusLane | None = None,
    review_state: CorpusReviewState | None = Query(default=None),
) -> list[SourceSummary]:
    return [presenters.source_summary(s) for s in service.list_sources(db, lane, review_state)]


@router.post("/sources", response_model=SourceDetail, status_code=status.HTTP_201_CREATED)
def upload_source(
    curator: Curator,
    db: DB,
    ctx: Ctx,
    file: Annotated[UploadFile, File()],
    lane: Annotated[CorpusLane, Form()],
    instrument_id: Annotated[uuid.UUID, Form()],
    title: Annotated[str, Form(min_length=1, max_length=500)],
    source_authority: Annotated[SourceAuthority, Form()],
    document_type: Annotated[CorpusDocumentType, Form()],
    retrieved_on: Annotated[date, Form()],
    source_url: Annotated[str | None, Form(max_length=2000)] = None,
    source_reference: Annotated[str | None, Form(max_length=1000)] = None,
    source_date: Annotated[date | None, Form()] = None,
) -> SourceDetail:
    """Store an official source file and where it came from. It is not read, and not approved."""
    max_bytes = get_settings().corpus_max_upload_bytes
    data = file.file.read(max_bytes + 1)  # at most limit+1, to detect an oversized file
    meta = service.SourceMetadata(
        lane=lane, instrument_id=instrument_id, title=title.strip(), source_authority=source_authority,
        document_type=document_type, retrieved_on=retrieved_on, source_url=source_url,
        source_reference=source_reference, source_date=source_date,
    )
    source = service.upload_source(
        db, curator, meta, filename=file.filename, declared_mime=file.content_type, data=data, ctx=ctx
    )
    return presenters.source_detail(db, source)


@router.get("/sources/{source_id}", response_model=SourceDetail)
def get_source(source_id: uuid.UUID, _: Reader, db: DB) -> SourceDetail:
    return presenters.source_detail(db, service.get_source(db, source_id))


@router.get("/sources/{source_id}/original")
def get_original(source_id: uuid.UUID, _: Reader, db: DB) -> Response:
    """The file exactly as uploaded, after checking it still is. Never rendered by this origin."""
    source = service.get_source(db, source_id)
    data = ingest.load_original(source)
    return Response(
        content=data,
        media_type=source.mime_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(source.file_name)}",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/sources/{source_id}/parse", response_model=SourceDetail)
def parse_source(source_id: uuid.UUID, curator: Curator, db: DB, ctx: Ctx) -> SourceDetail:
    return presenters.source_detail(db, service.parse_source(db, curator, source_id, ctx))


@router.get("/sources/{source_id}/text", response_model=SourceText)
def get_source_text(source_id: uuid.UUID, _: Reader, db: DB) -> SourceText:
    """The text as read, page by page, with the chunk boundaries. Exactly what will be reviewed."""
    source = service.get_source(db, source_id)
    if source.ingestion_state not in service.READ_STATES:
        raise Conflict("This source has not been read yet", code="source_not_read")
    return presenters.source_text(db, source)


@router.get("/sources/{source_id}/diff", response_model=DiffOut)
def get_source_diff(source_id: uuid.UUID, _: Reader, db: DB) -> DiffOut:
    baseline, diff = service.source_diff(db, service.get_source(db, source_id))
    return presenters.source_diff_out(baseline, diff)


@router.post("/sources/{source_id}/submit", response_model=SourceDetail)
def submit_source(source_id: uuid.UUID, curator: Curator, db: DB, ctx: Ctx) -> SourceDetail:
    return presenters.source_detail(db, service.submit_source(db, curator, source_id, ctx))


@router.post("/sources/{source_id}/approve", response_model=SourceDetail)
def approve_source(source_id: uuid.UUID, data: ApproveSource, curator: Curator, db: DB, ctx: Ctx) -> SourceDetail:
    source = service.approve_source(
        db, curator, source_id, expected_sha256=data.expected_sha256, acknowledge_issues=data.acknowledge_issues,
        ctx=ctx,
    )
    return presenters.source_detail(db, source)


@router.post("/sources/{source_id}/reject", response_model=SourceDetail)
def reject_source(source_id: uuid.UUID, data: Reject, curator: Curator, db: DB, ctx: Ctx) -> SourceDetail:
    return presenters.source_detail(db, service.reject_source(db, curator, source_id, reason=data.reason, ctx=ctx))


@router.post("/sources/{source_id}/versions", response_model=VersionDetail, status_code=status.HTTP_201_CREATED)
def create_version(source_id: uuid.UUID, data: VersionCreate, curator: Curator, db: DB, ctx: Ctx) -> VersionDetail:
    version = service.create_version(
        db, curator, source_id, provision_id=data.provision_id, char_start=data.char_start, char_end=data.char_end,
        valid_from=data.valid_from, valid_to=data.valid_to, ctx=ctx,
    )
    return presenters.version_detail(db, version)


# ---------- provision versions ----------


@router.get("/versions/{version_id}", response_model=VersionDetail)
def get_version(version_id: uuid.UUID, _: Reader, db: DB) -> VersionDetail:
    return presenters.version_detail(db, service.get_version(db, version_id))


@router.patch("/versions/{version_id}", response_model=VersionDetail)
def update_version(version_id: uuid.UUID, data: VersionUpdate, curator: Curator, db: DB, ctx: Ctx) -> VersionDetail:
    given = data.model_fields_set
    kwargs = {}
    if "valid_from" in given:
        kwargs["valid_from"] = data.valid_from
    if "valid_to" in given:
        kwargs["valid_to"] = data.valid_to
    version = service.update_version(
        db, curator, version_id, char_start=data.char_start, char_end=data.char_end, ctx=ctx, **kwargs
    )
    return presenters.version_detail(db, version)


@router.get("/versions/{version_id}/diff", response_model=DiffOut)
def get_version_diff(version_id: uuid.UUID, _: Reader, db: DB) -> DiffOut:
    baseline, diff = service.version_diff(db, service.get_version(db, version_id))
    return presenters.version_diff_out(baseline, diff)


@router.post("/versions/{version_id}/submit", response_model=VersionDetail)
def submit_version(version_id: uuid.UUID, curator: Curator, db: DB, ctx: Ctx) -> VersionDetail:
    return presenters.version_detail(db, service.submit_version(db, curator, version_id, ctx))


@router.post("/versions/{version_id}/approve", response_model=VersionDetail)
def approve_version(
    version_id: uuid.UUID, data: ApproveVersion, curator: Curator, db: DB, ctx: Ctx
) -> VersionDetail:
    version = service.approve_version(
        db, curator, version_id, expected_text_sha256=data.expected_text_sha256,
        acknowledge_issues=data.acknowledge_issues, ctx=ctx,
    )
    return presenters.version_detail(db, version)


@router.post("/versions/{version_id}/reject", response_model=VersionDetail)
def reject_version(version_id: uuid.UUID, data: Reject, curator: Curator, db: DB, ctx: Ctx) -> VersionDetail:
    return presenters.version_detail(db, service.reject_version(db, curator, version_id, reason=data.reason, ctx=ctx))


@router.post(
    "/versions/{version_id}/status-events", response_model=StatusEventOut, status_code=status.HTTP_201_CREATED
)
def record_status(
    version_id: uuid.UUID, data: StatusEventCreate, curator: Curator, db: DB, ctx: Ctx
) -> StatusEventOut:
    event = service.record_status(
        db, curator, version_id, status=data.status, effective_date=data.effective_date,
        basis_source_id=data.basis_source_id, basis_reference=data.basis_reference, note=data.note, ctx=ctx,
    )
    return presenters.status_event_out(db, event)


# ---------- queues ----------


@router.get("/review-queue", response_model=ReviewQueue)
def review_queue(_: Reader, db: DB) -> ReviewQueue:
    sources, versions = service.review_queue(db)
    return ReviewQueue(
        sources=[presenters.source_summary(s) for s in sources],
        versions=[presenters.version_summary(db, v) for v in versions],
    )


@router.get("/drafts", response_model=ReviewQueue)
def drafts(_: Reader, db: DB) -> ReviewQueue:
    sources, versions = service.drafts(db)
    return ReviewQueue(
        sources=[presenters.source_summary(s) for s in sources],
        versions=[presenters.version_summary(db, v) for v in versions],
    )
