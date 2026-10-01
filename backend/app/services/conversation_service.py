"""The history conversation's state machine.

    start
      → awaiting_answer        the engine chose a question, and recorded why
      → answer / decline       the patient's own words or taps, kept as given
      → candidates             what a free-text answer might contribute
      → not applicable         follow-ups whose branch stayed shut, recorded
      → …                      next applicable question
      → awaiting_confirmation  the configured flow has nothing left to ask
      → confirm / edit / reject each candidate
      → completed              "configured history flow complete"

Every decision in that diagram is made by `app.conversation.engine` — pure
functions over the flow and the answers, with no clock, no randomness and no
model. This module adds what the engine deliberately lacks: who may act,
persistence, idempotency, concurrency and audit. It makes no decision of its
own about what to ask.

Promises carried over from Phase 2, because they are the same promises:

* the patient's own words are never overwritten by a normalised form;
* a candidate is a suggestion until the patient acts on it, and completing the
  conversation acts on nothing;
* attribution comes from what was asked, never from a reading of the answer.

`completed` means the configured flow reached its end. It does not mean a
history is complete, and nothing here scores completeness.
"""

import functools
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.exc import StaleDataError

from app.conversation import engine
from app.conversation import flow as flows
from app.conversation.model import (
    FLOW_COMPLETE,
    REVIEW_STEP_ID,
    Answer,
    FlowDefinition,
    QuestionDefinition,
    Resolution,
    Status,
)
from app.core.languages import LanguageCode
from app.models import (
    ConversationCandidateFact,
    ConversationResponse,
    ConversationSession,
    ConversationSkip,
    MedicalRecord,
    PatientProfile,
    User,
)
from app.models.enums import (
    ConversationSection,
    ConversationStatus,
    FactReviewState,
    FactSubject,
    RecordSource,
    RecordStatus,
    RecordType,
)
from app.services import audit
from app.services.ai_facts import CATEGORY_TO_RECORD_TYPE, FAMILY_RECORDED_CATEGORIES
from app.services.audit import RequestContext
from app.services.errors import Conflict, InvalidInput, InvalidTransition, NotFound

# Which confirmed categories become a health record, and as what, is imported
# from Phase 2 rather than restated here (D-025). A second copy would be a
# second thing to keep true.

#: `MedicalRecord.title` is 200 characters. A candidate value may be longer;
#: the title is cut, the record's content keeps every word.
RECORD_TITLE_CHARS = 200

#: Statuses in which a conversation is still the patient's current one.
OPEN = (
    ConversationStatus.AWAITING_ANSWER,
    ConversationStatus.AWAITING_CONFIRMATION,
    ConversationStatus.PAUSED,
)
PAUSABLE = (ConversationStatus.AWAITING_ANSWER, ConversationStatus.AWAITING_CONFIRMATION)
#: A candidate in one of these states has been acted on by the patient.
ACTED_ON = (FactReviewState.CONFIRMED, FactReviewState.EDITED)


@dataclass
class SessionView:
    """A session, the flow it is walked under, and where every question stands."""

    session: ConversationSession
    flow: FlowDefinition
    resolution: Resolution

    @property
    def question(self) -> QuestionDefinition | None:
        qid = self.session.current_question_id
        return self.flow.question(qid) if qid else None

    @property
    def reason(self) -> str | None:
        """The reason code for the current question (or for reaching review)."""
        return self.session.current_question_reason

    @property
    def answered(self) -> int:
        return sum(1 for s in self.resolution.states if s.status in (Status.ANSWERED, Status.DECLINED))

    @property
    def remaining(self) -> int:
        return self.resolution.remaining

    @property
    def current_step(self) -> str | None:
        """The question id, the review step, or nothing once the conversation is closed."""
        if self.session.status == ConversationStatus.AWAITING_CONFIRMATION:
            return REVIEW_STEP_ID
        if self.session.status in (ConversationStatus.COMPLETED, ConversationStatus.ABANDONED):
            return None
        return self.session.current_question_id


def _now() -> datetime:
    return datetime.now(UTC)


def _guarded(fn):
    """Turn a lost race into a clean refusal.

    The session row is versioned: every UPDATE carries `WHERE revision = <the
    value read>`. When another request moved the conversation first, the
    database matches no row, SQLAlchemy raises, and nothing this request did is
    kept — its answer, its candidates and its audit lines roll back together.
    """

    @functools.wraps(fn)
    def wrapper(db: Session, *args, **kwargs):
        try:
            return fn(db, *args, **kwargs)
        except StaleDataError:
            db.rollback()
            raise Conflict(
                "This conversation moved on while that was being saved. Reload and try again",
                code="conversation_out_of_date",
            ) from None

    return wrapper


# --------------------------------------------------------------------------
# loading and authorization
# --------------------------------------------------------------------------


def _load(db: Session, session_id: uuid.UUID) -> ConversationSession | None:
    return db.scalar(
        select(ConversationSession)
        .where(ConversationSession.id == session_id)
        .options(
            selectinload(ConversationSession.responses),
            selectinload(ConversationSession.candidates),
            selectinload(ConversationSession.skips),
        )
        .execution_options(populate_existing=True)
    )


def get_own_session(db: Session, patient: PatientProfile, session_id: uuid.UUID) -> ConversationSession:
    """This patient's session, or nothing.

    Another patient's session is "not found", never "forbidden": telling someone
    a session exists is itself a disclosure. A doctor has no route here at all —
    a conversation reaches a clinician only through the records the patient
    confirmed and then chose to share.
    """
    session = _load(db, session_id)
    if session is None or session.patient_id != patient.id:
        raise NotFound("Conversation not found")
    return session


def flow_of(session: ConversationSession) -> FlowDefinition:
    """The flow this session started under — never the current one."""
    return flows.get_flow(session.flow_id, session.flow_version)


def _current_responses(session: ConversationSession) -> dict[str, ConversationResponse]:
    """The one current answer per question. Built from `sequence`, an explicit
    order, so the result never depends on the order rows came back in."""
    current: dict[str, ConversationResponse] = {}
    for response in sorted(session.responses, key=lambda r: r.sequence):
        if response.superseded_at is None:
            current[response.question_id] = response
    return current


def _answers(session: ConversationSession) -> dict[str, Answer]:
    return {
        qid: engine.answer_of(r.declined, r.answer_value)
        for qid, r in _current_responses(session).items()
    }


def _current_skips(session: ConversationSession) -> dict[str, ConversationSkip]:
    return {s.question_id: s for s in session.skips if s.superseded_at is None}


def view(session: ConversationSession) -> SessionView:
    flow = flow_of(session)
    return SessionView(session, flow, engine.resolve(flow, _answers(session)))


def current_session(db: Session, patient: PatientProfile) -> SessionView | None:
    """The conversation this patient is in the middle of, if there is one."""
    open_session = db.scalar(
        select(ConversationSession)
        .where(ConversationSession.patient_id == patient.id, ConversationSession.status.in_(OPEN))
        .order_by(ConversationSession.created_at.desc())
        .limit(1)
    )
    return view(_load(db, open_session.id)) if open_session is not None else None


def _next_sequence(rows) -> int:
    return max((r.sequence for r in rows), default=0) + 1


# --------------------------------------------------------------------------
# moving the conversation on
# --------------------------------------------------------------------------


def _reconcile_skips(
    db: Session, actor: User, session: ConversationSession, resolution: Resolution, ctx: RequestContext | None
) -> None:
    """Make the recorded "not asked" rows match what the engine now says.

    A question gets a skip row the first time its branch is known to be shut,
    and keeps it while that stays true. If a revised answer upstream reopens
    it, the row is superseded — never deleted — and the question is asked.
    """
    current = _current_skips(session)
    wanted = {s.question.id: s for s in resolution.not_applicable}
    now = _now()
    retired = False

    for qid, row in current.items():
        state = wanted.get(qid)
        still_true = (
            state is not None
            and state.reason_code == row.reason_code
            and state.trigger_question_id == row.trigger_question_id
        )
        if not still_true:
            row.superseded_at = now
            retired = True
            audit.record(
                db, actor=actor, action="conversation.question_reopened", resource_type="conversation",
                resource_id=session.id, patient_id=session.patient_id,
                details={
                    "question_id": qid,
                    "flow_version": session.flow_version,
                    "previous_reason_code": row.reason_code,
                    "transition_type": "reopened",
                },
                ctx=ctx,
            )
    if retired:
        # Before any replacement row is added, so the one-current-skip index
        # sees the old row retired first.
        db.flush()

    live = {qid for qid, row in current.items() if row.superseded_at is None}
    sequence = _next_sequence(session.skips)
    for state in resolution.not_applicable:
        qid = state.question.id
        if qid in live:
            continue
        session.skips.append(
            ConversationSkip(
                patient_id=session.patient_id,
                question_id=qid,
                question_version=state.question.version,
                flow_version=session.flow_version,
                section=state.question.section,
                reason_code=state.reason_code,
                trigger_question_id=state.trigger_question_id,
                predicate_id=state.predicate_id,
                sequence=sequence,
            )
        )
        sequence += 1
        audit.record(
            db, actor=actor, action="conversation.question_not_applicable", resource_type="conversation",
            resource_id=session.id, patient_id=session.patient_id,
            details={
                "question_id": qid,
                "question_version": state.question.version,
                "section": state.question.section.value,
                "flow_version": session.flow_version,
                "reason_code": state.reason_code,
                "trigger_question_id": state.trigger_question_id,
                "predicate_id": state.predicate_id,
                "transition_type": "not_applicable",
            },
            ctx=ctx,
        )


def _present(db: Session, actor: User, session: ConversationSession, ctx: RequestContext | None) -> Resolution:
    """Resolve the flow, record what was passed over, and put up the next question.

    Everything here is derived from the answers on record; nothing depends on
    the path taken to reach them. The same answers always produce the same
    current question, the same reason and the same skips.
    """
    flow = flow_of(session)
    resolution = engine.resolve(flow, _answers(session))
    _reconcile_skips(db, actor, session, resolution, ctx)
    selection = engine.select(resolution)
    previous = (session.current_question_id, session.status)

    if selection.question is None:
        session.current_question_id = None
        session.current_question_version = None
        session.current_section = ConversationSection.REVIEW
        session.current_question_reason = FLOW_COMPLETE
        session.current_trigger_question_id = None
        session.current_predicate_id = None
        session.status = ConversationStatus.AWAITING_CONFIRMATION
        if previous[1] != ConversationStatus.AWAITING_CONFIRMATION:
            audit.record(
                db, actor=actor, action="conversation.review_reached", resource_type="conversation",
                resource_id=session.id, patient_id=session.patient_id,
                details={
                    "step": REVIEW_STEP_ID,
                    "flow_version": session.flow_version,
                    "reason_code": FLOW_COMPLETE,
                    "transition_type": "review",
                },
                ctx=ctx,
            )
        return resolution

    q = selection.question
    session.current_question_id = q.id
    session.current_question_version = q.version
    session.current_section = q.section
    session.current_question_reason = selection.reason_code
    session.current_trigger_question_id = selection.trigger_question_id
    session.current_predicate_id = selection.predicate_id
    session.status = ConversationStatus.AWAITING_ANSWER
    # Logged when the engine selects a different question, not every time the
    # same one is shown again (after a resume, say): one selection, one line.
    if previous[0] != q.id:
        audit.record(
            db, actor=actor, action="conversation.question_presented", resource_type="conversation",
            resource_id=session.id, patient_id=session.patient_id,
            details={
                "question_id": q.id,
                "question_version": q.version,
                "section": q.section.value,
                "flow_version": session.flow_version,
                "reason_code": selection.reason_code,
                "trigger_question_id": selection.trigger_question_id,
                "predicate_id": selection.predicate_id,
                "transition_type": "presented",
            },
            ctx=ctx,
        )
    return resolution


# --------------------------------------------------------------------------
# lifecycle
# --------------------------------------------------------------------------


@_guarded
def start(
    db: Session,
    patient: PatientProfile,
    actor: User,
    language: LanguageCode,
    ctx: RequestContext | None = None,
    *,
    flow_version: int | None = None,
) -> SessionView:
    """Begin a history conversation, or hand back the one already open.

    `flow_version` exists for tests and for replaying an old flow on purpose. No
    request schema carries it: a patient cannot choose the tree they are asked.
    """
    existing = current_session(db, patient)
    if existing is not None:
        return existing

    flow = flows.current_flow() if flow_version is None else flows.get_flow(flows.FLOW_ID, flow_version)
    session = ConversationSession(
        patient_id=patient.id,
        flow_id=flow.flow_id,
        flow_version=flow.version,
        language=language,
    )
    db.add(session)
    try:
        db.flush()
    except IntegrityError:
        # Another request opened one first; the database allows only one.
        db.rollback()
        existing = current_session(db, patient)
        if existing is None:
            raise
        return existing

    audit.record(
        db, actor=actor, action="conversation.session_created", resource_type="conversation",
        resource_id=session.id, patient_id=patient.id,
        details={
            "flow": flow.flow_id,
            "flow_version": flow.version,
            "flow_status": flow.status.value,
            "language": language.value,
        },
        ctx=ctx,
    )
    _present(db, actor, session, ctx)
    db.commit()
    return view(_load(db, session.id))


@_guarded
def pause(
    db: Session, patient: PatientProfile, actor: User, session_id: uuid.UUID,
    ctx: RequestContext | None = None,
) -> SessionView:
    session = get_own_session(db, patient, session_id)
    if session.status not in PAUSABLE:
        raise InvalidTransition(f"A {session.status.value} conversation cannot be paused")
    session.status = ConversationStatus.PAUSED
    session.paused_at = _now()
    session.revision += 1
    audit.record(
        db, actor=actor, action="conversation.session_paused", resource_type="conversation",
        resource_id=session.id, patient_id=patient.id,
        details={"flow_version": session.flow_version, "transition_type": "paused"}, ctx=ctx,
    )
    db.commit()
    return view(_load(db, session.id))


@_guarded
def resume(
    db: Session, patient: PatientProfile, actor: User, session_id: uuid.UUID,
    ctx: RequestContext | None = None,
) -> SessionView:
    """Pick the conversation back up, on whatever the answers so far say is next."""
    session = get_own_session(db, patient, session_id)
    if session.status != ConversationStatus.PAUSED:
        raise InvalidTransition(f"A {session.status.value} conversation cannot be resumed")
    session.paused_at = None
    _present(db, actor, session, ctx)
    session.revision += 1
    audit.record(
        db, actor=actor, action="conversation.session_resumed", resource_type="conversation",
        resource_id=session.id, patient_id=patient.id,
        details={"flow_version": session.flow_version, "transition_type": "resumed"}, ctx=ctx,
    )
    db.commit()
    return view(_load(db, session.id))


@_guarded
def complete(
    db: Session, patient: PatientProfile, actor: User, session_id: uuid.UUID,
    ctx: RequestContext | None = None,
) -> SessionView:
    """Close the conversation: the configured flow is complete.

    Only from review, and only when the engine agrees nothing applicable is left.
    Completing confirms nothing: every candidate stays in whatever state the
    patient left it, and a pending one stays pending.
    """
    session = get_own_session(db, patient, session_id)
    if session.status != ConversationStatus.AWAITING_CONFIRMATION:
        raise InvalidTransition(
            f"A {session.status.value} conversation cannot be completed; "
            "every applicable question must be answered first"
        )
    resolution = view(session).resolution
    if resolution.next is not None:
        raise InvalidTransition("Questions in this conversation still need answers")

    session.status = ConversationStatus.COMPLETED
    session.completed_at = _now()
    session.revision += 1
    live = [c for c in session.candidates if c.superseded_at is None]
    audit.record(
        db, actor=actor, action="conversation.session_completed", resource_type="conversation",
        resource_id=session.id, patient_id=patient.id,
        details={
            "outcome": FLOW_COMPLETE,
            "flow_version": session.flow_version,
            "answered": sum(1 for s in resolution.states if s.status == Status.ANSWERED),
            "declined": sum(1 for s in resolution.states if s.status == Status.DECLINED),
            "not_applicable": len(resolution.not_applicable),
            "candidates": len(live),
            "still_pending": sum(1 for c in live if c.review_state == FactReviewState.PENDING),
            "transition_type": "completed",
        },
        ctx=ctx,
    )
    db.commit()
    return view(_load(db, session.id))


@_guarded
def abandon(
    db: Session, patient: PatientProfile, actor: User, session_id: uuid.UUID,
    ctx: RequestContext | None = None,
) -> SessionView:
    """Stop without finishing. The answers already given are kept."""
    session = get_own_session(db, patient, session_id)
    if session.status in (ConversationStatus.COMPLETED, ConversationStatus.ABANDONED):
        raise InvalidTransition(f"A {session.status.value} conversation cannot be abandoned")
    session.status = ConversationStatus.ABANDONED
    session.revision += 1
    audit.record(
        db, actor=actor, action="conversation.session_abandoned", resource_type="conversation",
        resource_id=session.id, patient_id=patient.id,
        details={"flow_version": session.flow_version, "transition_type": "abandoned"}, ctx=ctx,
    )
    db.commit()
    return view(_load(db, session.id))


# --------------------------------------------------------------------------
# answering
# --------------------------------------------------------------------------


def _replayed(session: ConversationSession, idempotency_key: str, question_id: str) -> bool:
    """Has this exact request already been recorded?

    Checked before anything else about the session, so a retry of an answer
    that moved the conversation into review still gets the success it earned
    rather than "this conversation is not waiting for an answer". A key reused
    for a different question is not a retry, and is refused.
    """
    earlier = next((r for r in session.responses if r.idempotency_key == idempotency_key), None)
    if earlier is None:
        return False
    if earlier.question_id != question_id:
        raise Conflict("That request key was already used for a different answer", code="idempotency_key_reused")
    return True


def _check_revision(session: ConversationSession, expected_revision: int | None) -> None:
    if expected_revision is not None and expected_revision != session.revision:
        raise Conflict(
            "This conversation moved on since you loaded it. Reload and try again",
            code="conversation_out_of_date",
        )


def _add_response(
    db: Session,
    session: ConversationSession,
    patient: PatientProfile,
    definition: QuestionDefinition,
    idempotency_key: str,
    answer_text: str | None,
    answer_value: dict[str, Any],
    declined: bool,
    reason: tuple[str | None, str | None, str | None],
) -> ConversationResponse:
    reason_code, trigger, predicate = reason
    response = ConversationResponse(
        patient_id=patient.id,
        question_id=definition.id,
        question_version=definition.version,
        section=definition.section,
        response_type=definition.response_type,
        answer_text=answer_text,
        answer_language=session.language if answer_text else None,
        answer_value=answer_value,
        declined=declined,
        reason_code=reason_code,
        trigger_question_id=trigger,
        predicate_id=predicate,
        sequence=_next_sequence(session.responses),
        idempotency_key=idempotency_key,
    )
    # Appended rather than added by foreign key, so the in-memory session sees
    # it when the engine picks what comes next.
    session.responses.append(response)
    db.flush()
    return response


def _add_candidate(
    db: Session,
    actor: User,
    session: ConversationSession,
    definition: QuestionDefinition,
    response: ConversationResponse,
    ctx: RequestContext | None,
) -> None:
    value = engine.candidate_value(definition, response.answer_text, response.declined)
    if not value:
        return
    candidate = ConversationCandidateFact(
        response_id=response.id,
        patient_id=session.patient_id,
        category=definition.category,
        # From the question, never from a reading of the answer.
        subject=definition.subject,
        subject_evidence=None,
        value=value,
        original_text=response.answer_text,
        review_state=FactReviewState.PENDING,
        position=_next_sequence_for_position(session.candidates),
    )
    session.candidates.append(candidate)
    db.flush()
    audit.record(
        db, actor=actor, action="conversation.candidate_created", resource_type="conversation",
        resource_id=session.id, patient_id=session.patient_id,
        details={
            "candidate_id": str(candidate.id),
            "category": definition.category.value,
            "subject": definition.subject.value,
            "question_id": definition.id,
            "response_id": str(response.id),
        },
        ctx=ctx,
    )


def _next_sequence_for_position(candidates) -> int:
    return max((c.position for c in candidates), default=0) + 1


def _lost_insert_race(
    db: Session, patient: PatientProfile, session_id: uuid.UUID, idempotency_key: str, question_id: str
) -> SessionView:
    """An insert collided with a row another request wrote a moment earlier.

    If that request was this same one retried, its answer is the answer. If it
    was a different answer to the same question, this one lost the race.
    """
    db.rollback()
    session = get_own_session(db, patient, session_id)
    if _replayed(session, idempotency_key, question_id):
        return view(session)
    raise Conflict(
        "This conversation moved on while that was being saved. Reload and try again",
        code="conversation_out_of_date",
    )


@_guarded
def submit_answer(
    db: Session,
    patient: PatientProfile,
    actor: User,
    session_id: uuid.UUID,
    question_id: str,
    idempotency_key: str,
    text: str | None = None,
    value: dict[str, Any] | None = None,
    declined: bool = False,
    expected_revision: int | None = None,
    ctx: RequestContext | None = None,
) -> SessionView:
    """Record an answer to the current question and move the conversation on.

    The client says what it is answering, never what to ask next. Every check
    runs before anything is written, so a refused request leaves the
    conversation exactly as it was.
    """
    session = get_own_session(db, patient, session_id)
    if _replayed(session, idempotency_key, question_id):
        return view(session)
    if session.status == ConversationStatus.PAUSED:
        raise InvalidTransition("This conversation is paused. Resume it before answering")
    if session.status != ConversationStatus.AWAITING_ANSWER:
        raise InvalidTransition(f"A {session.status.value} conversation is not waiting for an answer")
    _check_revision(session, expected_revision)
    if question_id != session.current_question_id:
        raise Conflict("That is not the question this conversation is waiting on", code="unexpected_question")

    definition = flow_of(session).question(question_id)
    if definition is None or definition.version != session.current_question_version:
        # Published flows are immutable, so this cannot happen without a bug.
        raise Conflict("That question is not the one this conversation showed", code="unexpected_question")

    answer_text, answer_value = engine.validate(definition, text, value, declined)

    try:
        response = _add_response(
            db, session, patient, definition, idempotency_key, answer_text, answer_value, declined,
            (session.current_question_reason, session.current_trigger_question_id, session.current_predicate_id),
        )
    except IntegrityError:
        return _lost_insert_race(db, patient, session_id, idempotency_key, question_id)

    audit.record(
        db, actor=actor, action="conversation.response_submitted", resource_type="conversation",
        resource_id=session.id, patient_id=patient.id,
        details={
            "question_id": definition.id,
            "question_version": definition.version,
            "section": definition.section.value,
            "flow_version": session.flow_version,
            "response_id": str(response.id),
            "response_type": definition.response_type.value,
            "reason_code": response.reason_code,
            "declined": declined,
            "transition_type": "declined" if declined else "answered",
        },
        ctx=ctx,
    )
    _add_candidate(db, actor, session, definition, response, ctx)

    session.revision += 1
    _present(db, actor, session, ctx)
    db.commit()
    return view(_load(db, session.id))


@_guarded
def revise_answer(
    db: Session,
    patient: PatientProfile,
    actor: User,
    session_id: uuid.UUID,
    question_id: str,
    idempotency_key: str,
    text: str | None = None,
    value: dict[str, Any] | None = None,
    declined: bool = False,
    expected_revision: int | None = None,
    ctx: RequestContext | None = None,
) -> SessionView:
    """Replace an earlier answer. The earlier one stays, superseded.

    A correction can change which follow-ups apply. Any answered follow-up that
    stops applying is retired along with it — it answered a question that,
    given the correction, would not have been asked — and any follow-up that
    starts applying is asked next. The engine works both out before anything is
    written.

    Refused when something drawn from an affected answer has already been
    confirmed: that fact is in the patient's record now, and it changes through
    the record (or by rejecting the candidate first), never as a side effect.
    """
    session = get_own_session(db, patient, session_id)
    if _replayed(session, idempotency_key, question_id):
        return view(session)
    if session.status == ConversationStatus.PAUSED:
        raise InvalidTransition("This conversation is paused. Resume it before changing an answer")
    if session.status not in PAUSABLE:
        raise InvalidTransition(f"Answers in a {session.status.value} conversation cannot be changed")
    _check_revision(session, expected_revision)

    flow = flow_of(session)
    definition = flow.question(question_id)
    if definition is None:
        raise NotFound("Question not found")
    current = _current_responses(session)
    earlier = current.get(question_id)
    state = view(session).resolution.by_id[question_id]
    if earlier is None or state.status not in (Status.ANSWERED, Status.DECLINED):
        # Covers a question not yet reached, the one currently being asked, and
        # one the engine did not ask — a question that was not asked has no
        # answer to change, and cannot be given one this way.
        raise Conflict("That question has no answer to change", code="question_not_answered")

    answer_text, answer_value = engine.validate(definition, text, value, declined)
    _, invalidated = engine.plan_revision(
        flow, _answers(session), question_id, engine.answer_of(declined, answer_value)
    )

    affected = [earlier] + [current[s.question.id] for s in invalidated]
    affected_ids = {r.id for r in affected}
    drawn = [c for c in session.candidates if c.superseded_at is None and c.response_id in affected_ids]
    if any(c.review_state in ACTED_ON for c in drawn):
        raise Conflict(
            "Something from that answer is already confirmed in your record. Reject it first to change the answer",
            code="answer_has_confirmed_facts",
        )

    now = _now()
    no_longer_applicable = {s.question.id for s in invalidated}
    for response in affected:
        response.superseded_at = now
        audit.record(
            db, actor=actor, action="conversation.response_superseded", resource_type="conversation",
            resource_id=session.id, patient_id=patient.id,
            details={
                "question_id": response.question_id,
                "response_id": str(response.id),
                "flow_version": session.flow_version,
                "cause": "no_longer_applicable" if response.question_id in no_longer_applicable else "revised",
                "transition_type": "superseded",
            },
            ctx=ctx,
        )
    for candidate in drawn:
        candidate.superseded_at = now
        audit.record(
            db, actor=actor, action="conversation.candidate_superseded", resource_type="conversation",
            resource_id=session.id, patient_id=patient.id,
            details={"candidate_id": str(candidate.id), "category": candidate.category.value},
            ctx=ctx,
        )
    # Retire the old answers before writing the new one, so the database's
    # one-current-answer rule sees them go first.
    db.flush()

    try:
        replacement = _add_response(
            db, session, patient, definition, idempotency_key, answer_text, answer_value, declined,
            # Why the question was asked has not changed; only the answer has.
            (earlier.reason_code, earlier.trigger_question_id, earlier.predicate_id),
        )
    except IntegrityError:
        return _lost_insert_race(db, patient, session_id, idempotency_key, question_id)

    audit.record(
        db, actor=actor, action="conversation.answer_revised", resource_type="conversation",
        resource_id=session.id, patient_id=patient.id,
        details={
            "question_id": question_id,
            "question_version": definition.version,
            "flow_version": session.flow_version,
            "previous_response_id": str(earlier.id),
            "response_id": str(replacement.id),
            "no_longer_applicable": sorted(no_longer_applicable),
            "declined": declined,
            "transition_type": "revised",
        },
        ctx=ctx,
    )
    _add_candidate(db, actor, session, definition, replacement, ctx)

    session.revision += 1
    _present(db, actor, session, ctx)
    db.commit()
    return view(_load(db, session.id))


# --------------------------------------------------------------------------
# review
# --------------------------------------------------------------------------


@dataclass
class ReviewItem:
    question: QuestionDefinition
    #: answered | declined | not_applicable | current
    outcome: str
    response: ConversationResponse | None
    reason_code: str | None
    trigger_question_id: str | None
    predicate_id: str | None


@dataclass
class ReviewCandidate:
    candidate: ConversationCandidateFact
    #: The health record confirming it would create, or `None` when it would
    #: create none (a symptom stays with the problem it describes, D-025).
    becomes: RecordType | None


@dataclass
class Review:
    view: SessionView
    items: list[ReviewItem]
    candidates: list[ReviewCandidate]


def review(db: Session, patient: PatientProfile, session_id: uuid.UUID) -> Review:
    """Everything the patient needs before finishing, in the flow's own order.

    What they answered, what they chose not to answer, what was not asked and
    why, what is still open, and what each candidate would become if they
    confirmed it. Reading this changes nothing: no candidate is confirmed by
    being shown.
    """
    session = get_own_session(db, patient, session_id)
    v = view(session)
    current = _current_responses(session)
    skips = _current_skips(session)

    items: list[ReviewItem] = []
    for state in v.resolution.states:
        q = state.question
        if state.status in (Status.ANSWERED, Status.DECLINED):
            r = current[q.id]
            items.append(ReviewItem(
                q, state.status.value, r,
                # The reason recorded when it was asked; rows from before 5B
                # carry none, and the engine's reason stands in.
                r.reason_code or state.reason_code,
                r.trigger_question_id if r.reason_code else state.trigger_question_id,
                r.predicate_id if r.reason_code else state.predicate_id,
            ))
        elif state.status == Status.NOT_APPLICABLE:
            skip = skips.get(q.id)
            items.append(ReviewItem(
                q, "not_applicable", None,
                skip.reason_code if skip else state.reason_code,
                skip.trigger_question_id if skip else state.trigger_question_id,
                skip.predicate_id if skip else state.predicate_id,
            ))
        elif state.status == Status.OPEN and q.id == session.current_question_id:
            items.append(ReviewItem(
                q, "current", None,
                session.current_question_reason, session.current_trigger_question_id, session.current_predicate_id,
            ))
        # Questions not reached yet are not listed: nothing is known about them.

    candidates = [
        ReviewCandidate(c, _record_type_for(c))
        for c in sorted(session.candidates, key=lambda c: c.position)
        if c.superseded_at is None
    ]
    return Review(v, items, candidates)


# --------------------------------------------------------------------------
# confirmation
# --------------------------------------------------------------------------


def get_own_candidate(db: Session, patient: PatientProfile, candidate_id: uuid.UUID) -> ConversationCandidateFact:
    candidate = db.get(ConversationCandidateFact, candidate_id)
    if candidate is None or candidate.patient_id != patient.id:
        raise NotFound("Item not found")
    return candidate


@_guarded
def review_candidate(
    db: Session,
    patient: PatientProfile,
    actor: User,
    candidate_id: uuid.UUID,
    action: str,
    value: str | None = None,
    session_id: uuid.UUID | None = None,
    ctx: RequestContext | None = None,
) -> ConversationCandidateFact:
    """Confirm, edit or reject one candidate. The only way a candidate changes state.

    Confirming a category that maps to a health record writes one, carrying the
    patient's own words as its content — the same rule Phase 2 follows.
    Rejecting removes any record a previous confirmation created.
    """
    candidate = get_own_candidate(db, patient, candidate_id)
    # When the caller named a conversation, the candidate must be from it — a
    # correct-looking id from the wrong conversation is not found, not accepted.
    if session_id is not None and candidate.session_id != session_id:
        raise NotFound("Item not found")
    if candidate.superseded_at is not None:
        raise InvalidTransition(
            "The answer this came from was changed, so it can no longer be acted on",
            code="candidate_superseded",
        )

    if action == "confirm":
        candidate.review_state = FactReviewState.CONFIRMED
    elif action == "edit":
        if not value or not value.strip():
            raise InvalidInput("A corrected value is required")
        candidate.edited_value = value.strip()[: engine.MAX_VALUE_CHARS]
        candidate.review_state = FactReviewState.EDITED
    elif action == "reject":
        candidate.review_state = FactReviewState.REJECTED
    else:
        raise InvalidInput("Unknown action")

    candidate.reviewed_at = _now()
    candidate.reviewed_by_user_id = actor.id
    # Acting on a candidate changes the conversation's state, so it moves the
    # session's revision like any other transition. A revision of the answer
    # this candidate came from, racing this confirmation, then loses cleanly
    # instead of retiring a candidate whose record has just been written.
    session = db.get(ConversationSession, candidate.session_id)
    session.revision += 1

    if candidate.review_state == FactReviewState.REJECTED:
        _remove_record(db, candidate)
    else:
        _sync_record(db, patient, actor, candidate)

    audit.record(
        db, actor=actor, action=f"conversation.candidate_{candidate.review_state.value}",
        resource_type="conversation", resource_id=candidate.session_id, patient_id=patient.id,
        details={
            "candidate_id": str(candidate.id),
            "category": candidate.category.value,
            "subject": candidate.subject.value,
        },
        ctx=ctx,
    )
    db.commit()
    db.refresh(candidate)
    return candidate


def _record_type_for(candidate: ConversationCandidateFact) -> RecordType | None:
    """Which health record a confirmed candidate becomes, if any.

    A relative's information becomes family history and nothing else — the same
    rule as Phase 2, because a father's allergy is not the patient's allergy
    whether it arrived in a paragraph or through a question.
    """
    if candidate.subject == FactSubject.SELF:
        return CATEGORY_TO_RECORD_TYPE.get(candidate.category)
    if candidate.subject == FactSubject.FAMILY:
        return RecordType.FAMILY_HISTORY if candidate.category in FAMILY_RECORDED_CATEGORIES else None
    # "other" or "unknown" attribution never writes to the patient's record.
    return None


def _sync_record(
    db: Session, patient: PatientProfile, actor: User, candidate: ConversationCandidateFact
) -> None:
    record_type = _record_type_for(candidate)
    if record_type is None:
        return

    session = db.get(ConversationSession, candidate.session_id)
    # The title is the value and nothing else — no English decoration, which no
    # catalogue could translate — cut to the column's length. The content keeps
    # every word the patient wrote.
    title = candidate.effective_value[:RECORD_TITLE_CHARS]

    if candidate.medical_record_id:
        existing = db.get(MedicalRecord, candidate.medical_record_id)
        if existing is not None:
            existing.title = title
            return

    record = MedicalRecord(
        patient_id=patient.id,
        type=record_type,
        title=title,
        content=candidate.original_text or candidate.effective_value,
        source=RecordSource.PATIENT,
        source_language=session.language if session else patient.preferred_language,
        status=RecordStatus.ACTIVE,
        recorded_by_user_id=actor.id,
    )
    db.add(record)
    db.flush()
    candidate.medical_record_id = record.id


def _remove_record(db: Session, candidate: ConversationCandidateFact) -> None:
    if not candidate.medical_record_id:
        return
    record = db.get(MedicalRecord, candidate.medical_record_id)
    if record is not None:
        db.delete(record)
    candidate.medical_record_id = None
