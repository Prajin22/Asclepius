"""Patient confirmation of AI-extracted facts.

An extracted fact is a *suggestion* until the patient acts on it. Confirming a
fact in a category that maps to the health record creates a record marked
`ai_extracted`, carrying the patient's original wording; rejecting removes any
record previously created from it. Every action is audited.
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.languages import DEFAULT_LANGUAGE, LanguageCode
from app.models import AIExtractedFact, DocumentPage, MedicalDocument, MedicalRecord, PatientProfile, User
from app.models.enums import (
    FactCategory,
    FactReviewState,
    FactSubject,
    RecordSource,
    RecordStatus,
    RecordType,
)
from app.services import audit
from app.services.audit import RequestContext
from app.services.errors import InvalidInput, NotFound

# Categories that become the patient's own health records when confirmed.
# Symptoms, durations and measurements stay attached to the problem they came from.
CATEGORY_TO_RECORD_TYPE: dict[FactCategory, RecordType] = {
    FactCategory.ALLERGY: RecordType.ALLERGY,
    FactCategory.MEDICATION: RecordType.MEDICATION,
    FactCategory.MEDICAL_HISTORY: RecordType.HISTORY_NOTE,
}

# A relative's information is recorded as family history and nothing else.
# A father's penicillin allergy must never become the patient's allergy.
FAMILY_RECORDED_CATEGORIES = {
    FactCategory.ALLERGY,
    FactCategory.MEDICATION,
    FactCategory.MEDICAL_HISTORY,
    FactCategory.SYMPTOM,
}


def record_type_for(fact: AIExtractedFact) -> RecordType | None:
    """Which health record, if any, a confirmed fact becomes."""
    if fact.subject == FactSubject.SELF:
        return CATEGORY_TO_RECORD_TYPE.get(fact.category)
    if fact.subject == FactSubject.FAMILY:
        return RecordType.FAMILY_HISTORY if fact.category in FAMILY_RECORDED_CATEGORIES else None
    # "other" or "unknown" attribution never writes to the patient's record.
    return None


def get_own_fact(db: Session, patient: PatientProfile, fact_id: uuid.UUID) -> AIExtractedFact:
    fact = db.get(AIExtractedFact, fact_id)
    if fact is None or fact.patient_id != patient.id:
        raise NotFound("Extracted item not found")
    return fact


def list_facts_for_records(
    db: Session, patient_id: uuid.UUID, record_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[AIExtractedFact]]:
    if not record_ids:
        return {}
    grouped: dict[uuid.UUID, list[AIExtractedFact]] = {}
    for fact in db.scalars(
        select(AIExtractedFact)
        .where(AIExtractedFact.patient_id == patient_id, AIExtractedFact.source_id.in_(record_ids))
        .order_by(AIExtractedFact.position)
    ):
        grouped.setdefault(fact.source_id, []).append(fact)
    return grouped


def act_on_fact(
    db: Session,
    patient: PatientProfile,
    actor: User,
    fact_id: uuid.UUID,
    action: str,
    value: str | None = None,
    ctx: RequestContext | None = None,
) -> AIExtractedFact:
    fact = get_own_fact(db, patient, fact_id)

    if action == "confirm":
        fact.review_state = FactReviewState.CONFIRMED
    elif action == "edit":
        if not value or not value.strip():
            raise InvalidInput("A corrected value is required")
        fact.edited_value = value.strip()[:300]
        fact.review_state = FactReviewState.EDITED
    elif action == "reject":
        fact.review_state = FactReviewState.REJECTED
    else:
        raise InvalidInput("Unknown action")

    fact.reviewed_at = datetime.now().astimezone()
    fact.reviewed_by_user_id = actor.id

    if fact.review_state == FactReviewState.REJECTED:
        _remove_record(db, fact)
    else:
        _sync_record(db, patient, actor, fact)

    audit.record(
        db, actor=actor, action=f"ai.fact_{fact.review_state.value}", resource_type="ai_fact",
        resource_id=fact.id, patient_id=patient.id,
        details={"category": fact.category.value, "source_record_id": str(fact.source_id)}, ctx=ctx,
    )
    db.commit()
    db.refresh(fact)
    return fact


def source_language_for(db: Session, fact: AIExtractedFact) -> LanguageCode:
    """Language of the text a fact came from: a record, or a document page."""
    if fact.source_type == "medical_record":
        record = db.get(MedicalRecord, fact.source_id)
        if record is not None:
            return record.source_language
    elif fact.source_type == "document_page":
        page = db.get(DocumentPage, fact.source_id)
        if page is not None:
            if page.detected_language:
                return page.detected_language
            document = db.get(MedicalDocument, page.document_id)
            if document is not None and document.source_language:
                return document.source_language
    return DEFAULT_LANGUAGE


def _sync_record(db: Session, patient: PatientProfile, actor: User, fact: AIExtractedFact) -> None:
    record_type = record_type_for(fact)
    if record_type is None:
        return
    language = source_language_for(db, fact)

    title = fact.effective_value
    if fact.subject == FactSubject.FAMILY:
        # Make the attribution unmistakable wherever the record is shown,
        # including after the patient edits the value.
        relative = (fact.subject_evidence or "family member").strip()
        title = f"{fact.effective_value} ({relative})"

    if fact.medical_record_id:
        existing = db.get(MedicalRecord, fact.medical_record_id)
        if existing is not None:
            existing.title = title
            return

    record = MedicalRecord(
        patient_id=patient.id,
        type=record_type,
        title=title,
        # The patient's own words stay the content; the English value is the title.
        content=fact.original_text or fact.evidence_quote,
        source=RecordSource.AI_EXTRACTED,
        source_language=language,
        status=RecordStatus.ACTIVE,
        recorded_by_user_id=actor.id,
    )
    db.add(record)
    db.flush()
    fact.medical_record_id = record.id


def _remove_record(db: Session, fact: AIExtractedFact) -> None:
    if not fact.medical_record_id:
        return
    record = db.get(MedicalRecord, fact.medical_record_id)
    if record is not None and record.source == RecordSource.AI_EXTRACTED:
        db.delete(record)
    fact.medical_record_id = None
