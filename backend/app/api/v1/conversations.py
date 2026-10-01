"""The patient's history conversation. All logic lives in the service layer.

Every route is under `/patients/me`, and every one resolves the patient from
the token. There is deliberately no doctor-facing route here: a conversation
reaches a clinician only through the health records the patient confirmed and
then shared, which is the mechanism that already exists.

No route accepts a "next question" or a flow version — the server decides what
comes next from the answers given, under the flow the conversation started
with, and says why.
"""

import uuid

from fastapi import APIRouter

from app.api.deps import DB, Ctx, CurrentPatient
from app.schemas.conversation import (
    AnswerIn,
    AnswerRevisionIn,
    CandidateActionIn,
    CandidateOut,
    ConversationDetailOut,
    ConversationStartIn,
    ReviewOut,
)
from app.services import conversation_presenters as present
from app.services import conversation_service as conversations
from app.services.errors import NotFound

router = APIRouter(prefix="/patients/me/conversations", tags=["patient-conversation"])


@router.post("", response_model=ConversationDetailOut, status_code=201)
def start(
    data: ConversationStartIn, patient: CurrentPatient, db: DB, ctx: Ctx
) -> ConversationDetailOut:
    """Begin a history conversation, or hand back the one already open."""
    view = conversations.start(
        db, patient, patient.user, data.language or patient.preferred_language, ctx
    )
    return present.conversation_detail(view)


@router.get("/current", response_model=ConversationDetailOut)
def current(patient: CurrentPatient, db: DB) -> ConversationDetailOut:
    """The conversation this patient is in the middle of."""
    view = conversations.current_session(db, patient)
    if view is None:
        raise NotFound("No conversation in progress")
    return present.conversation_detail(view)


@router.get("/{session_id}", response_model=ConversationDetailOut)
def get(session_id: uuid.UUID, patient: CurrentPatient, db: DB) -> ConversationDetailOut:
    session = conversations.get_own_session(db, patient, session_id)
    return present.conversation_detail(conversations.view(session))


@router.post("/{session_id}/answers", response_model=ConversationDetailOut)
def answer(
    session_id: uuid.UUID, data: AnswerIn, patient: CurrentPatient, db: DB, ctx: Ctx
) -> ConversationDetailOut:
    """Record an answer. The server picks what comes next, and records why."""
    view = conversations.submit_answer(
        db,
        patient,
        patient.user,
        session_id,
        data.question_id,
        data.idempotency_key,
        text=data.text,
        value=data.value.model_dump(exclude_none=True) if data.value else None,
        declined=data.declined,
        expected_revision=data.expected_revision,
        ctx=ctx,
    )
    return present.conversation_detail(view)


@router.post("/{session_id}/answers/{question_id}/revision", response_model=ConversationDetailOut)
def revise(
    session_id: uuid.UUID,
    question_id: str,
    data: AnswerRevisionIn,
    patient: CurrentPatient,
    db: DB,
    ctx: Ctx,
) -> ConversationDetailOut:
    """Replace an earlier answer. The earlier one is kept, superseded, and the
    server works out which follow-ups now apply."""
    view = conversations.revise_answer(
        db,
        patient,
        patient.user,
        session_id,
        question_id,
        data.idempotency_key,
        text=data.text,
        value=data.value.model_dump(exclude_none=True) if data.value else None,
        declined=data.declined,
        expected_revision=data.expected_revision,
        ctx=ctx,
    )
    return present.conversation_detail(view)


@router.get("/{session_id}/review", response_model=ReviewOut)
def review(session_id: uuid.UUID, patient: CurrentPatient, db: DB) -> ReviewOut:
    """What was answered, declined, not asked and why, and what each candidate
    would become. Reading it changes nothing."""
    return present.review(conversations.review(db, patient, session_id))


@router.post("/{session_id}/pause", response_model=ConversationDetailOut)
def pause(session_id: uuid.UUID, patient: CurrentPatient, db: DB, ctx: Ctx) -> ConversationDetailOut:
    return present.conversation_detail(
        conversations.pause(db, patient, patient.user, session_id, ctx)
    )


@router.post("/{session_id}/resume", response_model=ConversationDetailOut)
def resume(session_id: uuid.UUID, patient: CurrentPatient, db: DB, ctx: Ctx) -> ConversationDetailOut:
    return present.conversation_detail(
        conversations.resume(db, patient, patient.user, session_id, ctx)
    )


@router.post("/{session_id}/complete", response_model=ConversationDetailOut)
def complete(session_id: uuid.UUID, patient: CurrentPatient, db: DB, ctx: Ctx) -> ConversationDetailOut:
    """Close the conversation once every applicable question has been answered."""
    return present.conversation_detail(
        conversations.complete(db, patient, patient.user, session_id, ctx)
    )


@router.post("/{session_id}/abandon", response_model=ConversationDetailOut)
def abandon(session_id: uuid.UUID, patient: CurrentPatient, db: DB, ctx: Ctx) -> ConversationDetailOut:
    """Stop without finishing. The answers already given are kept."""
    return present.conversation_detail(
        conversations.abandon(db, patient, patient.user, session_id, ctx)
    )


@router.post("/{session_id}/candidates/{candidate_id}", response_model=CandidateOut)
def act_on_candidate(
    session_id: uuid.UUID,
    candidate_id: uuid.UUID,
    data: CandidateActionIn,
    patient: CurrentPatient,
    db: DB,
    ctx: Ctx,
) -> CandidateOut:
    """Confirm, edit or reject one thing an answer produced."""
    candidate = conversations.review_candidate(
        db, patient, patient.user, candidate_id, data.action, data.value,
        session_id=session_id, ctx=ctx,
    )
    return CandidateOut.model_validate(candidate)
