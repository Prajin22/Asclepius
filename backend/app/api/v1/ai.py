"""Patient-facing AI endpoints. All logic lives in the service layer."""

import uuid

from fastapi import APIRouter

from app.api.deps import DB, Ctx, CurrentPatient
from app.models import AIArtifact
from app.schemas.ai import AIArtifactOut, AIConsentUpdate, AIFactAction, AIFactOut, AIProcessingOut
from app.schemas.patient import PatientProfileOut
from app.services import ai_facts, ai_pipeline, ai_presenters, presenters
from app.services.errors import NotFound

router = APIRouter(prefix="/patients/me", tags=["patient-ai"])


@router.put("/ai-consent", response_model=PatientProfileOut)
def update_consent(data: AIConsentUpdate, patient: CurrentPatient, db: DB, ctx: Ctx) -> PatientProfileOut:
    """Explicit opt-in/out for AI processing of this patient's information."""
    updated = ai_pipeline.set_consent(db, patient, patient.user, data.granted, ctx)
    return presenters.patient_profile(updated)


@router.post("/records/{record_id}/ai-process", response_model=AIProcessingOut)
async def process_record(record_id: uuid.UUID, patient: CurrentPatient, db: DB, ctx: Ctx) -> AIProcessingOut:
    """Run detect → normalise → extract over one record. The record is unchanged."""
    record = ai_pipeline.get_own_record(db, patient, record_id)
    result = await ai_pipeline.process_record(db, patient, patient.user, record, ctx)
    return ai_presenters.processing_out(result)


@router.get("/records/{record_id}/ai", response_model=AIProcessingOut)
def record_ai_state(record_id: uuid.UUID, patient: CurrentPatient, db: DB) -> AIProcessingOut:
    record = ai_pipeline.get_own_record(db, patient, record_id)
    return ai_presenters.processing_out(ai_pipeline.get_record_state(db, patient, record))


@router.post("/ai/facts/{fact_id}", response_model=AIFactOut)
def review_fact(
    fact_id: uuid.UUID, data: AIFactAction, patient: CurrentPatient, db: DB, ctx: Ctx
) -> AIFactOut:
    """Confirm, edit or reject one AI-extracted item."""
    fact = ai_facts.act_on_fact(db, patient, patient.user, fact_id, data.action, data.value, ctx)
    return AIFactOut.model_validate(fact)


@router.get("/ai/artifacts/{artifact_id}", response_model=AIArtifactOut)
def get_artifact(artifact_id: uuid.UUID, patient: CurrentPatient, db: DB) -> AIArtifactOut:
    artifact = db.get(AIArtifact, artifact_id)
    if artifact is None or artifact.patient_id != patient.id:
        raise NotFound("AI artifact not found")
    return AIArtifactOut.model_validate(artifact)
