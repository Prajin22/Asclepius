"""Turning conversation state into what a browser receives.

The only place a question definition becomes a payload. No wording appears
here — prompts, options, help and reasons travel as keys and codes, and the
browser resolves them — so translating anything can never rewrite what a
patient was recorded as having seen.
"""

from app.conversation.model import QuestionDefinition
from app.models import ConversationResponse
from app.models.enums import ConversationStatus, FactReviewState
from app.schemas.conversation import (
    CandidateOut,
    ConversationDetailOut,
    ConversationOut,
    OptionOut,
    QuestionOut,
    ReasonOut,
    ResponseOut,
    ReviewCandidateOut,
    ReviewCountsOut,
    ReviewItemOut,
    ReviewOut,
)
from app.services.conversation_service import Review, SessionView


def reason(code: str | None, trigger: str | None = None, predicate: str | None = None) -> ReasonOut | None:
    return ReasonOut(code=code, trigger_question_id=trigger, predicate_id=predicate) if code else None


def question(definition: QuestionDefinition, why: ReasonOut | None = None) -> QuestionOut:
    return QuestionOut(
        id=definition.id,
        version=definition.version,
        section=definition.section,
        response_type=definition.response_type,
        prompt_key=definition.prompt_key,
        help_key=definition.help_key,
        options=[OptionOut(id=o.id, label_key=o.label_key, exclusive=o.exclusive) for o in definition.options],
        required=definition.required,
        reason=why,
    )


def response(r: ConversationResponse) -> ResponseOut:
    return ResponseOut(
        id=r.id,
        question_id=r.question_id,
        question_version=r.question_version,
        section=r.section,
        response_type=r.response_type,
        answer_text=r.answer_text,
        answer_language=r.answer_language,
        answer_value=r.answer_value or {},
        declined=r.declined,
        reason=reason(r.reason_code, r.trigger_question_id, r.predicate_id),
        sequence=r.sequence,
        created_at=r.created_at,
    )


def _fields(v: SessionView) -> dict:
    s = v.session
    current = v.question
    return {
        "id": s.id,
        "flow_id": s.flow_id,
        "flow_version": s.flow_version,
        "flow_status": v.flow.status.value,
        "clinical_review": v.flow.clinical_review.value,
        "status": s.status,
        "language": s.language,
        "revision": s.revision,
        "current_section": s.current_section,
        "current_step": v.current_step,
        "question": question(
            current, reason(s.current_question_reason, s.current_trigger_question_id, s.current_predicate_id)
        )
        if current is not None and s.status in (ConversationStatus.AWAITING_ANSWER, ConversationStatus.PAUSED)
        else None,
        "answered": v.answered,
        "remaining": v.remaining,
        "started_at": s.started_at,
        "paused_at": s.paused_at,
        "completed_at": s.completed_at,
    }


def conversation(v: SessionView) -> ConversationOut:
    return ConversationOut(**_fields(v))


def conversation_detail(v: SessionView) -> ConversationDetailOut:
    s = v.session
    return ConversationDetailOut(
        **_fields(v),
        responses=[response(r) for r in sorted(s.responses, key=lambda r: r.sequence) if r.superseded_at is None],
        candidates=[
            CandidateOut.model_validate(c)
            for c in sorted(s.candidates, key=lambda c: c.position)
            if c.superseded_at is None
        ],
    )


def review(data: Review) -> ReviewOut:
    items = [
        ReviewItemOut(
            question_id=i.question.id,
            question_version=i.question.version,
            section=i.question.section,
            response_type=i.question.response_type,
            prompt_key=i.question.prompt_key,
            outcome=i.outcome,
            response=response(i.response) if i.response is not None else None,
            reason=reason(i.reason_code, i.trigger_question_id, i.predicate_id),
        )
        for i in data.items
    ]
    candidates = [
        ReviewCandidateOut(**CandidateOut.model_validate(c.candidate).model_dump(), becomes=c.becomes)
        for c in data.candidates
    ]
    states = [c.candidate.review_state for c in data.candidates]
    status = data.view.session.status
    return ReviewOut(
        conversation=conversation(data.view),
        can_complete=status == ConversationStatus.AWAITING_CONFIRMATION and data.view.resolution.next is None,
        items=items,
        candidates=candidates,
        counts=ReviewCountsOut(
            answered=sum(1 for i in data.items if i.outcome == "answered"),
            declined=sum(1 for i in data.items if i.outcome == "declined"),
            not_applicable=sum(1 for i in data.items if i.outcome == "not_applicable"),
            candidates_pending=states.count(FactReviewState.PENDING),
            candidates_confirmed=states.count(FactReviewState.CONFIRMED),
            candidates_edited=states.count(FactReviewState.EDITED),
            candidates_rejected=states.count(FactReviewState.REJECTED),
        ),
    )
