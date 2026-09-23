"""The authorised source bundle for one consultation (Phase 4).

Everything a provider is allowed to see, and nothing else. The bundle is built
*after* the authorization boundary closes and *before* anything is sent, so
there is no point at which a model could be shown something and asked to ignore
it.

Two properties do most of the safety work here:

**Opaque references.** Each authorised item gets a short handle — ``S1``, ``S2``
— valid only inside this one bundle. The model is never shown a database
identifier, a document id, a page offset or a bounding box, so it cannot invent
one, cannot leak one, and cannot cite an item that was not shared: an unshared
row simply has no handle. A hallucinated ``S99`` fails to resolve and the item
carrying it is dropped.

**Content, not ids, in the hash.** Shared records are live references (D-006) —
a patient can edit one after sharing it. So the canonical form covers what each
item *says*, which is what makes a stale summary detectable at all.

Nothing here interprets medical meaning. It selects, orders and redacts.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.languages import LanguageCode
from app.models import AIArtifact, AIExtractedFact, Consultation, DocumentPage
from app.models.enums import (
    AIArtifactStatus,
    AIOperation,
    AuthorizationBasis,
    BundleItemKind,
    FactReviewState,
    RecordType,
    SummaryItemOrigin,
)
from app.services.consultation_service import AuthorizedContext

#: Caps on what reaches a provider. Sharing limits are much higher (a patient may
#: share 200 records); a prompt is not the place to prove it. Anything trimmed is
#: reported in `truncated` and surfaced to the doctor rather than dropped quietly.
MAX_CURRENT_PROBLEMS = 10
MAX_HEALTH_RECORDS = 40
MAX_FACTS = 120
MAX_DOCUMENTS = 20
MAX_PRIOR_CONSULTATIONS = 20
MAX_PRIOR_PRESCRIPTIONS = 20

#: Longest source text handed to a provider, per item.
MAX_TEXT_CHARS = 2000

#: Facts the patient has decided to stand behind. Pending facts are counted but
#: never stated (Stage A decision 2); rejected facts never leave the database.
CONFIRMED_STATES = (FactReviewState.CONFIRMED, FactReviewState.EDITED)


def _clip(text: str | None) -> str | None:
    if text is None:
        return None
    text = text.strip()
    return text[:MAX_TEXT_CHARS] if text else None


def _iso(value: datetime | date | None) -> str | None:
    return value.isoformat() if value is not None else None


@dataclass(frozen=True)
class BundleItem:
    """One authorised source, in two halves.

    `payload` is what a provider sees — words, no identifiers. `resolution` is
    what the application keeps to itself, and is how a returned ``S7`` becomes a
    real row again. The two never travel together.
    """

    ref: str
    kind: BundleItemKind
    origin: SummaryItemOrigin
    authorization_basis: AuthorizationBasis
    payload: dict[str, Any]
    resolution: dict[str, Any]
    #: The text this item asserts, used to check that a statement citing it is
    #: actually supported by it.
    support_text: str = ""


@dataclass
class SourceBundle:
    consultation_id: uuid.UUID
    patient_id: uuid.UUID
    items: list[BundleItem] = field(default_factory=list)
    #: Extracted facts still awaiting the patient's decision.
    pending_fact_count: int = 0
    truncated: list[str] = field(default_factory=list)
    #: Minimal identity, exactly what the case view already shows a doctor.
    patient: dict[str, Any] = field(default_factory=dict)
    requested_at: datetime | None = None

    @property
    def by_ref(self) -> dict[str, BundleItem]:
        return {item.ref: item for item in self.items}

    def provider_payload(self) -> dict[str, Any]:
        """Exactly what is sent to a provider. Audited by eye in one place."""
        return {
            "consultation": {
                "requested_at": _iso(self.requested_at),
                "patient": self.patient,
            },
            "pending_fact_count": self.pending_fact_count,
            "items": [item.payload for item in self.items],
        }

    def canonical(self) -> str:
        """Stable text form of the bundle's *content*.

        Deterministic across processes: sorted keys, fixed separators, no
        whitespace drift. `requested_at` is included because it is a property of
        the consultation, not of this build; nothing time-of-build is.
        """
        return json.dumps(
            self.provider_payload(), sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )

    def hash(self) -> str:
        return hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()


class _Refs:
    """Hands out S1, S2, S3… in build order, so the same state gives the same refs."""

    def __init__(self) -> None:
        self._n = 0

    def next(self) -> str:
        self._n += 1
        return f"S{self._n}"


def _patient_identity(context: AuthorizedContext) -> dict[str, Any]:
    """Age, sex and language — the same minimal identity the case view shows.

    No name, no email, no phone, no emergency contact. A summary does not need
    to know who the patient is to organise what they said.
    """
    patient = context.consultation.patient
    return {
        "age": patient.age_on(date.today()),
        "sex": patient.sex.value,
        "preferred_language": patient.preferred_language.value,
    }


def _statement_payload(text: str, language: LanguageCode | None, **extra: Any) -> dict[str, Any]:
    """The content half of a patient-authored item. `add()` supplies ref and kind.

    `content_kind` is always "text" today. It exists so that a future transcript
    of speech can enter the bundle as a different content kind without changing
    this schema or anything downstream of it — Phase 6 is not implemented, but
    the shape does not assume text is the only possibility.
    """
    payload: dict[str, Any] = {
        "content_kind": "text",
        "text": text,
        "language": language.value if language else None,
    }
    payload.update({k: v for k, v in extra.items() if v is not None})
    return payload


def _english_for_records(
    db: Session, patient_id: uuid.UUID, records: list
) -> dict[uuid.UUID, str]:
    """The stored English rendering of each record, where one exists.

    A doctor reads the summary in English, but a patient writes in their own
    language. The English already exists as a `normalization` artifact and the
    doctor already sees it in the case view, so including it here shows the
    provider nothing new — it just means an English summary does not have to be
    translated a second time. Records that were never processed simply have no
    English, and their own words travel alone.
    """
    if not records:
        return {}
    wanted = {hashlib.sha256((r.content or "").encode("utf-8")).hexdigest(): r.id for r in records}
    english: dict[uuid.UUID, str] = {}
    for artifact in db.scalars(
        select(AIArtifact)
        .where(
            AIArtifact.patient_id == patient_id,
            AIArtifact.artifact_type == AIOperation.NORMALIZATION.value,
            AIArtifact.status == AIArtifactStatus.SUCCEEDED,
            AIArtifact.source_hash.in_(list(wanted)),
        )
        .order_by(AIArtifact.created_at.desc())
    ):
        record_id = wanted.get(artifact.source_hash or "")
        if record_id is None or record_id in english:
            continue
        # The artifact must actually reference this record, not merely share its text.
        if not any(ref.get("id") == str(record_id) for ref in artifact.source_references or []):
            continue
        text = (artifact.content or {}).get("normalized_english")
        if text:
            english[record_id] = text
    return english


def _facts_for_sources(
    db: Session, patient_id: uuid.UUID, source_ids: list[uuid.UUID]
) -> tuple[list[AIExtractedFact], int]:
    """Confirmed facts on these sources, plus how many are still pending."""
    if not source_ids:
        return [], 0
    rows = list(
        db.scalars(
            select(AIExtractedFact)
            .where(
                AIExtractedFact.patient_id == patient_id,
                AIExtractedFact.source_id.in_(source_ids),
            )
            .order_by(AIExtractedFact.position)
        )
    )
    confirmed = [f for f in rows if f.review_state in CONFIRMED_STATES]
    pending = sum(1 for f in rows if f.review_state == FactReviewState.PENDING)
    return confirmed, pending


def build_source_bundle(db: Session, context: AuthorizedContext) -> SourceBundle:
    """Turn an authorised context into the deterministic bundle a provider sees."""
    c: Consultation = context.consultation
    refs = _Refs()
    bundle = SourceBundle(
        consultation_id=c.id,
        patient_id=c.patient_id,
        patient=_patient_identity(context),
        requested_at=c.created_at,
    )

    def add(
        kind: BundleItemKind,
        origin: SummaryItemOrigin,
        basis: AuthorizationBasis,
        payload_extra: dict[str, Any],
        resolution: dict[str, Any],
        support_text: str,
    ) -> str:
        ref = refs.next()
        payload = {"ref": ref, "kind": kind.value, **payload_extra}
        bundle.items.append(
            BundleItem(
                ref=ref,
                kind=kind,
                origin=origin,
                authorization_basis=basis,
                payload=payload,
                resolution={"ref": ref, "kind": kind.value, "authorization_basis": basis.value, **resolution},
                support_text=support_text,
            )
        )
        return ref

    # 1. The patient's message to this doctor, in their own words.
    if c.request_message:
        text = _clip(c.request_message) or ""
        add(
            BundleItemKind.PATIENT_STATEMENT,
            SummaryItemOrigin.PATIENT_PROVIDED,
            AuthorizationBasis.PATIENT_GRANT,
            _statement_payload(text, c.request_language, recorded_at=_iso(c.created_at)),
            {"consultation_id": str(c.id), "language": c.request_language.value if c.request_language else None,
             "original_text": text, "occurred_at": _iso(c.created_at)},
            text,
        )

    # 2. Shared health records. Current problems first — they are why the patient came.
    problems = context.current_problems[:MAX_CURRENT_PROBLEMS]
    if len(context.current_problems) > MAX_CURRENT_PROBLEMS:
        bundle.truncated.append("current_problem")
    history = context.medical_history[:MAX_HEALTH_RECORDS]
    if len(context.medical_history) > MAX_HEALTH_RECORDS:
        bundle.truncated.append("health_record")

    selected_records = [*problems, *history]
    english = _english_for_records(db, c.patient_id, selected_records)

    record_refs: dict[uuid.UUID, str] = {}
    for record in selected_records:
        kind = (
            BundleItemKind.CURRENT_PROBLEM
            if record.type == RecordType.CURRENT_PROBLEM
            else BundleItemKind.HEALTH_RECORD
        )
        text = _clip(record.content) or ""
        rendering = _clip(english.get(record.id))
        ref = add(
            kind,
            SummaryItemOrigin.PATIENT_PROVIDED,
            AuthorizationBasis.PATIENT_GRANT,
            {
                "content_kind": "text",
                "text": text,
                # The patient's own words stay first and stay whole; this is the
                # machine rendering beside them, never instead of them.
                "english": rendering,
                "language": record.source_language.value,
                "record_type": record.type.value,
                "title": _clip(record.title),
                "recorded_at": _iso(record.created_at),
            },
            {
                "record_id": str(record.id),
                "language": record.source_language.value,
                "original_text": text,
                "occurred_at": _iso(record.created_at),
            },
            # A statement may be supported by either the original or its English.
            f"{text} {rendering or ''}",
        )
        record_refs[record.id] = ref

    # 3. Shared documents. Metadata only: raw page text is the largest
    #    prompt-injection surface, and confirmed facts already carry the quotes
    #    that make every claim traceable.
    documents = context.documents[:MAX_DOCUMENTS]
    if len(context.documents) > MAX_DOCUMENTS:
        bundle.truncated.append("document")
    document_refs: dict[uuid.UUID, str] = {}
    for doc in documents:
        ref = add(
            BundleItemKind.DOCUMENT,
            SummaryItemOrigin.PATIENT_PROVIDED,
            AuthorizationBasis.PATIENT_GRANT,
            {
                "title": _clip(doc.title) or doc.file_name,
                "document_type": doc.document_type.value,
                "uploaded_at": _iso(doc.uploaded_at),
                "language": doc.source_language.value if doc.source_language else None,
            },
            {"document_id": str(doc.id), "occurred_at": _iso(doc.uploaded_at)},
            _clip(doc.title) or doc.file_name,
        )
        document_refs[doc.id] = ref

    # 4. Confirmed facts, from shared records and from pages of shared documents.
    page_ids: list[uuid.UUID] = []
    if documents:
        page_ids = list(
            db.scalars(
                select(DocumentPage.id)
                .where(
                    DocumentPage.document_id.in_([d.id for d in documents]),
                    DocumentPage.patient_id == c.patient_id,
                    DocumentPage.superseded_at.is_(None),
                )
                .order_by(DocumentPage.page_number)
            )
        )
    fact_sources = [*record_refs.keys(), *page_ids]
    facts, pending = _facts_for_sources(db, c.patient_id, fact_sources)
    bundle.pending_fact_count = pending
    if len(facts) > MAX_FACTS:
        bundle.truncated.append("fact")
        facts = facts[:MAX_FACTS]

    for fact in facts:
        from_ref = record_refs.get(fact.source_id)
        document_ref = document_refs.get(fact.evidence_document_id) if fact.evidence_document_id else None
        value = fact.effective_value
        add(
            BundleItemKind.FACT,
            SummaryItemOrigin.PATIENT_CONFIRMED,
            AuthorizationBasis.PATIENT_GRANT,
            {
                "category": fact.category.value,
                # Attribution travels with the fact so the model can group a
                # relative's history separately. It is re-attached from here on
                # the way out, so the model cannot change it.
                "subject": fact.subject.value,
                "subject_evidence": fact.subject_evidence,
                "value": value,
                "original_text": _clip(fact.original_text),
                "quote": _clip(fact.evidence_quote),
                "from": from_ref or document_ref,
                "page": fact.evidence_page_number,
            },
            {
                "fact_id": str(fact.id),
                "record_id": str(fact.source_id) if fact.source_type == "medical_record" else None,
                "document_id": str(fact.evidence_document_id) if fact.evidence_document_id else None,
                "page_number": fact.evidence_page_number,
                "bbox": fact.evidence_bbox,
                "quote": fact.evidence_quote,
                "original_text": fact.original_text,
                "subject": fact.subject.value,
                "subject_evidence": fact.subject_evidence,
            },
            f"{value} {fact.original_text or ''} {fact.evidence_quote or ''}",
        )

    # 5. Prior consultations. Doctor-authored, and it stays that way: the
    #    assessment travels verbatim and is never rewritten into a new claim.
    priors = [(x, AuthorizationBasis.PATIENT_GRANT) for x in context.shared_consultations]
    priors += [(x, AuthorizationBasis.OWN_PRIOR_CONSULTATION) for x in context.own_previous_consultations]
    if len(priors) > MAX_PRIOR_CONSULTATIONS:
        bundle.truncated.append("prior_consultation")
        priors = priors[:MAX_PRIOR_CONSULTATIONS]
    for prior, basis in priors:
        assessment = _clip(prior.doctor_assessment)
        add(
            BundleItemKind.PRIOR_CONSULTATION,
            SummaryItemOrigin.DOCTOR_AUTHORED,
            basis,
            {
                "doctor": prior.doctor.name,
                "specialization": prior.doctor.specialization,
                "status": prior.status.value,
                "completed_at": _iso(prior.completed_at),
                "created_at": _iso(prior.created_at),
                "doctor_assessment": assessment,
            },
            {
                "consultation_id": str(prior.id),
                "doctor_name": prior.doctor.name,
                "quote": assessment,
                "occurred_at": _iso(prior.completed_at or prior.created_at),
            },
            assessment or "",
        )

    # 6. Prior prescriptions. Organised, never compared, never resolved.
    prescriptions = context.shared_prescriptions[:MAX_PRIOR_PRESCRIPTIONS]
    if len(context.shared_prescriptions) > MAX_PRIOR_PRESCRIPTIONS:
        bundle.truncated.append("prior_prescription")
    for rx in prescriptions:
        items = [
            {
                "medication": item.medication,
                "dosage": item.dosage,
                "frequency": item.frequency,
                "duration": item.duration,
            }
            for item in rx.items
        ]
        add(
            BundleItemKind.PRIOR_PRESCRIPTION,
            SummaryItemOrigin.DOCTOR_AUTHORED,
            AuthorizationBasis.PATIENT_GRANT,
            {
                "doctor": rx.doctor.name,
                "issued_at": _iso(rx.created_at),
                "items": items,
                "instructions": _clip(rx.instructions),
            },
            {
                "prescription_id": str(rx.id),
                "doctor_name": rx.doctor.name,
                "occurred_at": _iso(rx.created_at),
            },
            " ".join(i["medication"] for i in items),
        )

    return bundle
