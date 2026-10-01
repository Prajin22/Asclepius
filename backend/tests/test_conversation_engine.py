"""The history conversation's state machine, at the domain level.

These drive `conversation_service` directly rather than through HTTP, because
what is being checked is the machine: which question comes next, what an answer
turns into, who may touch it, and what happens when the same request arrives
twice. The HTTP surface is tested separately.

Nothing here asserts that a particular question is clinically correct. The flow
is configuration; these tests check that the engine walks it honestly.
"""

import uuid

import pytest
from sqlalchemy import select

from app.conversation import flow
from app.core.languages import LanguageCode
from app.models import AuditEvent, MedicalRecord, PatientProfile
from app.models.enums import (
    ConversationStatus,
    FactReviewState,
    FactSubject,
    RecordSource,
    RecordType,
    ResponseType,
)
from app.services import conversation_service as cs
from app.services.errors import Conflict, InvalidInput, InvalidTransition, NotFound

TAMIL_COMPLAINT = "எனக்கு மூன்று நாட்களாக தலைவலி"


@pytest.fixture(autouse=True)
def _history_general_v1(monkeypatch):
    """These tests exercise history_general v1, the Phase 5A flow.

    New conversations start on v2 since Phase 5B, but v1 stays supported for
    every session started under it, so everything here must keep holding. The
    v2 tree has its own tests (test_conversation_tree*.py).
    """
    monkeypatch.setattr(flow, "FLOW_VERSION", 1)


@pytest.fixture
def actor(db, make_patient):
    """A patient profile and the user behind it."""
    created = make_patient()
    profile = db.get(PatientProfile, uuid.UUID(created.id))
    return profile, profile.user


def _key() -> str:
    return uuid.uuid4().hex


def _valid_answer(definition) -> dict:
    """A well-formed answer for whichever response type the question uses."""
    if definition.response_type == ResponseType.FREE_TEXT:
        return {"text": f"an answer to {definition.id}"}
    if definition.response_type == ResponseType.DURATION:
        return {"value": {"duration": {"amount": 3, "unit": "days"}}}
    if definition.response_type == ResponseType.MULTI_CHOICE:
        return {"value": {"choices": [definition.options[0].id]}}
    # yes/no and single choice
    return {"value": {"choices": [definition.options[0].id]}}


def _answer(db, patient, user, session_id, **overrides):
    """Answer whatever the session is currently waiting on."""
    view = cs.view(cs.get_own_session(db, patient, session_id))
    payload = _valid_answer(view.question) | overrides
    return cs.submit_answer(
        db, patient, user, session_id, view.question.id, _key(), **payload
    )


def _drive_to_end(db, patient, user, session_id, limit: int = 40):
    """Answer every question until the flow runs out of them."""
    view = cs.view(cs.get_own_session(db, patient, session_id))
    steps = 0
    while view.question is not None:
        steps += 1
        assert steps < limit, "the engine kept asking questions; it is not advancing"
        view = _answer(db, patient, user, session_id)
    return view


# --------------------------------------------------------------------------
# 1–4  starting, the first question, answering, advancing
# --------------------------------------------------------------------------


def test_starting_a_conversation_records_the_flow_it_started_under(db, actor):
    patient, user = actor
    view = cs.start(db, patient, user, LanguageCode.TA)

    assert view.session.flow_id == flow.FLOW_ID
    assert view.session.flow_version == flow.FLOW_VERSION
    assert view.session.status == ConversationStatus.AWAITING_ANSWER
    assert view.session.language == LanguageCode.TA
    assert view.answered == 0
    assert view.remaining > 0


def test_the_first_question_is_the_open_one_about_the_problem(db, actor):
    patient, user = actor
    view = cs.start(db, patient, user, LanguageCode.EN)

    # The conversation opens by letting the patient say what is wrong in their
    # own words, before anything narrows it down.
    assert view.question.id == "problem.description"
    assert view.question.response_type == ResponseType.FREE_TEXT
    assert view.reason


def test_starting_twice_continues_the_same_conversation(db, actor):
    patient, user = actor
    first = cs.start(db, patient, user, LanguageCode.EN)
    _answer(db, patient, user, first.session.id)

    second = cs.start(db, patient, user, LanguageCode.EN)

    # A reload must not leave the patient with two half-finished histories.
    assert second.session.id == first.session.id
    assert second.answered == 1


def test_an_answer_is_stored_in_the_patients_own_words(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.TA)

    after = cs.submit_answer(
        db, patient, user, started.session.id, "problem.description", _key(),
        text=TAMIL_COMPLAINT,
    )

    stored = after.session.responses[0]
    assert stored.answer_text == TAMIL_COMPLAINT
    assert stored.question_id == "problem.description"
    assert stored.question_version == 1


def test_answering_moves_the_conversation_to_the_next_question(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    # Read now: the view hands back the same live session object each time, so
    # comparing the two views' `.revision` would compare a value with itself.
    before = started.session.revision

    after = _answer(db, patient, user, started.session.id)

    assert after.question.id != "problem.description"
    assert after.answered == 1
    assert after.session.current_question_id == after.question.id
    assert after.session.revision > before


# --------------------------------------------------------------------------
# 5–6  branching and skipping
# --------------------------------------------------------------------------


def test_saying_there_is_no_pain_skips_the_pain_questions(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    sid = started.session.id

    _answer(db, patient, user, sid, text="I have been feeling very tired")
    _answer(db, patient, user, sid)  # duration
    _answer(db, patient, user, sid)  # happened before
    after = cs.submit_answer(
        db, patient, user, sid, "symptom.is_pain", _key(), value={"choices": ["no"]}
    )

    asked = [r.question_id for r in after.session.responses]
    end = _drive_to_end(db, patient, user, sid)
    everything_asked = [r.question_id for r in end.session.responses]

    assert "symptom.is_pain" in asked
    for pain_question in ("symptom.site", "symptom.character", "symptom.radiates"):
        assert pain_question not in everything_asked


def test_saying_there_is_pain_asks_where_it_is(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    sid = started.session.id

    _answer(db, patient, user, sid)  # problem
    _answer(db, patient, user, sid)  # duration
    _answer(db, patient, user, sid)  # happened before
    after = cs.submit_answer(
        db, patient, user, sid, "symptom.is_pain", _key(), value={"choices": ["yes"]}
    )

    assert after.question.id == "symptom.site"
    # And the reason is recorded, so "why was I asked this?" has an answer later.
    assert "pain" in after.session.current_question_reason


def test_an_optional_question_may_be_passed_over_and_a_required_one_may_not(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    sid = started.session.id

    # problem.description is required.
    with pytest.raises(InvalidInput):
        cs.submit_answer(
            db, patient, user, sid, "problem.description", _key(), declined=True
        )

    _answer(db, patient, user, sid)
    _answer(db, patient, user, sid)  # duration
    # symptom.happened_before is optional.
    after = cs.submit_answer(
        db, patient, user, sid, "symptom.happened_before", _key(), declined=True
    )

    declined = [r for r in after.session.responses if r.declined]
    assert [r.question_id for r in declined] == ["symptom.happened_before"]
    assert declined[0].answer_text is None
    # Passing over a question produces nothing to review.
    assert not [c for c in after.session.candidates if c.response_id == declined[0].id]


# --------------------------------------------------------------------------
# 7–10  candidates, and what the patient does with them
# --------------------------------------------------------------------------


def test_an_answer_produces_a_candidate_that_is_only_a_suggestion(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.TA)

    after = cs.submit_answer(
        db, patient, user, started.session.id, "problem.description", _key(),
        text=TAMIL_COMPLAINT,
    )

    candidate = after.session.candidates[0]
    assert candidate.review_state == FactReviewState.PENDING
    assert candidate.original_text == TAMIL_COMPLAINT
    # Nothing has been written to the patient's record yet.
    assert candidate.medical_record_id is None
    assert db.scalars(select(MedicalRecord).where(MedicalRecord.patient_id == patient.id)).all() == []


def test_confirming_a_candidate_writes_a_record_carrying_the_patients_words(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.TA)
    sid = started.session.id
    _answer(db, patient, user, sid)  # problem
    _answer(db, patient, user, sid)  # duration
    _answer(db, patient, user, sid)  # happened before
    cs.submit_answer(db, patient, user, sid, "symptom.is_pain", _key(), value={"choices": ["no"]})
    _drive_to_end(db, patient, user, sid)

    session = cs.get_own_session(db, patient, sid)
    allergy = next(c for c in session.candidates if c.category.value == "allergy")
    confirmed = cs.review_candidate(db, patient, user, allergy.id, "confirm")

    assert confirmed.review_state == FactReviewState.CONFIRMED
    record = db.get(MedicalRecord, confirmed.medical_record_id)
    assert record is not None
    assert record.type == RecordType.ALLERGY
    assert record.content == allergy.original_text
    assert record.source == RecordSource.PATIENT
    assert record.source_language == LanguageCode.TA


def test_editing_a_candidate_keeps_the_original_answer_beside_the_correction(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    after = cs.submit_answer(
        db, patient, user, started.session.id, "problem.description", _key(),
        text="bad hedache since tuesday",
    )
    candidate = after.session.candidates[0]

    edited = cs.review_candidate(db, patient, user, candidate.id, "edit", value="headache")

    assert edited.review_state == FactReviewState.EDITED
    assert edited.edited_value == "headache"
    assert edited.effective_value == "headache"
    # The correction sits beside what the patient typed; it does not replace it.
    assert edited.original_text == "bad hedache since tuesday"


def test_rejecting_a_candidate_removes_any_record_it_had_created(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    sid = started.session.id
    _answer(db, patient, user, sid)
    _answer(db, patient, user, sid)
    _answer(db, patient, user, sid)
    cs.submit_answer(db, patient, user, sid, "symptom.is_pain", _key(), value={"choices": ["no"]})
    _drive_to_end(db, patient, user, sid)

    session = cs.get_own_session(db, patient, sid)
    allergy = next(c for c in session.candidates if c.category.value == "allergy")
    confirmed = cs.review_candidate(db, patient, user, allergy.id, "confirm")
    record_id = confirmed.medical_record_id
    assert record_id is not None

    rejected = cs.review_candidate(db, patient, user, allergy.id, "reject")

    assert rejected.review_state == FactReviewState.REJECTED
    assert rejected.medical_record_id is None
    assert db.get(MedicalRecord, record_id) is None


def test_an_edit_needs_something_to_put_in_place_of_the_value(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    after = cs.submit_answer(
        db, patient, user, started.session.id, "problem.description", _key(), text="dizzy"
    )

    with pytest.raises(InvalidInput):
        cs.review_candidate(db, patient, user, after.session.candidates[0].id, "edit", value="   ")


# --------------------------------------------------------------------------
# 11–13  pause, resume, completion
# --------------------------------------------------------------------------


def test_a_conversation_can_be_paused_and_picked_back_up(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    sid = started.session.id
    _answer(db, patient, user, sid)
    waiting_on = cs.view(cs.get_own_session(db, patient, sid)).question.id

    paused = cs.pause(db, patient, user, sid)
    assert paused.session.status == ConversationStatus.PAUSED
    assert paused.session.paused_at is not None

    resumed = cs.resume(db, patient, user, sid)
    assert resumed.session.status == ConversationStatus.AWAITING_ANSWER
    assert resumed.session.paused_at is None
    # It picks up on the same question, and the earlier answer is still there.
    assert resumed.question.id == waiting_on
    assert resumed.answered == 1


def test_a_paused_conversation_does_not_take_answers(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    sid = started.session.id
    cs.pause(db, patient, user, sid)

    with pytest.raises(InvalidTransition):
        cs.submit_answer(
            db, patient, user, sid, "problem.description", _key(), text="still hurting"
        )


def test_answering_everything_moves_to_review_and_then_completes(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    sid = started.session.id

    end = _drive_to_end(db, patient, user, sid)

    assert end.question is None
    assert end.remaining == 0
    assert end.session.status == ConversationStatus.AWAITING_CONFIRMATION

    completed = cs.complete(db, patient, user, sid)
    assert completed.session.status == ConversationStatus.COMPLETED
    assert completed.session.completed_at is not None


def test_a_conversation_cannot_be_completed_while_questions_remain(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)

    with pytest.raises(InvalidTransition):
        cs.complete(db, patient, user, started.session.id)


# --------------------------------------------------------------------------
# 14  invalid transitions
# --------------------------------------------------------------------------


def test_a_completed_conversation_is_closed_to_everything(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    sid = started.session.id
    _drive_to_end(db, patient, user, sid)
    cs.complete(db, patient, user, sid)

    with pytest.raises(InvalidTransition):
        cs.pause(db, patient, user, sid)
    with pytest.raises(InvalidTransition):
        cs.complete(db, patient, user, sid)
    with pytest.raises(InvalidTransition):
        cs.abandon(db, patient, user, sid)


def test_an_active_conversation_cannot_be_resumed(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)

    with pytest.raises(InvalidTransition):
        cs.resume(db, patient, user, started.session.id)


def test_abandoning_keeps_the_answers_already_given(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    sid = started.session.id
    _answer(db, patient, user, sid, text="chest feels tight")

    abandoned = cs.abandon(db, patient, user, sid)

    assert abandoned.session.status == ConversationStatus.ABANDONED
    assert abandoned.session.responses[0].answer_text == "chest feels tight"


# --------------------------------------------------------------------------
# 15–16  duplicates and replays
# --------------------------------------------------------------------------


def test_the_same_request_twice_records_one_answer(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    sid = started.session.id
    key = _key()

    first = cs.submit_answer(
        db, patient, user, sid, "problem.description", key, text="sharp pain in my side"
    )
    revision_after_first = first.session.revision
    question_after_first = first.question.id

    second = cs.submit_answer(
        db, patient, user, sid, "problem.description", key, text="sharp pain in my side"
    )

    assert first.answered == second.answered == 1
    assert len(second.session.responses) == 1
    assert len(second.session.candidates) == 1
    # And the replay leaves the conversation exactly where it was.
    assert second.question.id == question_after_first
    assert second.session.revision == revision_after_first


def test_answering_a_question_the_engine_is_not_on_is_refused(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)

    # The client does not get to choose where the conversation goes.
    with pytest.raises(Conflict):
        cs.submit_answer(
            db, patient, user, started.session.id, "allergy.which", _key(), text="penicillin"
        )


def test_an_answer_built_against_a_stale_view_is_refused(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    sid = started.session.id
    stale_revision = started.session.revision
    _answer(db, patient, user, sid)

    with pytest.raises(Conflict) as raised:
        cs.submit_answer(
            db, patient, user, sid, "symptom.duration", _key(),
            value={"duration": {"amount": 2, "unit": "days"}},
            expected_revision=stale_revision,
        )

    assert raised.value.code == "conversation_out_of_date"


# --------------------------------------------------------------------------
# 17–19  who may touch a conversation
# --------------------------------------------------------------------------


def test_another_patients_conversation_is_not_found(db, actor, make_patient):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)

    other = db.get(PatientProfile, uuid.UUID(make_patient(email="other@example.com").id))

    # "Not found", not "forbidden": confirming it exists is itself a disclosure.
    with pytest.raises(NotFound):
        cs.get_own_session(db, other, started.session.id)
    with pytest.raises(NotFound):
        cs.submit_answer(
            db, other, other.user, started.session.id, "problem.description", _key(), text="hello"
        )


def test_another_patient_cannot_review_a_candidate(db, actor, make_patient):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    after = cs.submit_answer(
        db, patient, user, started.session.id, "problem.description", _key(), text="fever"
    )
    candidate = after.session.candidates[0]

    other = db.get(PatientProfile, uuid.UUID(make_patient(email="other@example.com").id))

    with pytest.raises(NotFound):
        cs.review_candidate(db, other, other.user, candidate.id, "confirm")
    assert db.get(type(candidate), candidate.id).review_state == FactReviewState.PENDING


def test_a_doctor_has_no_way_into_a_conversation(db, actor, make_doctor):
    patient, user = actor
    cs.start(db, patient, user, LanguageCode.EN)
    doctor = make_doctor()

    # Every entry point in the service takes the patient's own profile, and a
    # doctor account has none — a conversation reaches a clinician only through
    # records the patient confirmed and then shared.
    assert db.scalar(
        select(PatientProfile).where(PatientProfile.user_id == uuid.UUID(doctor.user_id))
    ) is None


def test_a_missing_conversation_is_not_found(db, actor):
    patient, _ = actor
    with pytest.raises(NotFound):
        cs.get_own_session(db, patient, uuid.uuid4())


# --------------------------------------------------------------------------
# 20–21  versions
# --------------------------------------------------------------------------


def test_an_answer_stays_readable_after_the_question_is_reworded(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    sid = started.session.id
    _answer(db, patient, user, sid, text="cough")
    after = _answer(db, patient, user, sid)  # symptom.duration, in v1's wording
    stored = next(r for r in after.session.responses if r.question_id == "symptom.duration")
    assert stored.question_version == 1

    # The wording has since moved on: v2 asks symptom.duration as version 2.
    assert flow.get_flow(flow.FLOW_ID, 2).question("symptom.duration").version == 2

    # The stored answer still resolves — to the wording it was actually given under.
    shown = cs.flow_of(after.session).question("symptom.duration")
    assert shown.version == stored.question_version == 1
    assert shown.prompt_key == "conversation.q.symptom.duration"


def test_a_session_remembers_the_flow_version_it_started_under(db, actor, monkeypatch):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    assert started.session.flow_version == 1

    monkeypatch.setattr(flow, "FLOW_VERSION", 2)

    # The tree changing does not retroactively reinterpret this conversation.
    reloaded = cs.get_own_session(db, patient, started.session.id)
    assert reloaded.flow_version == 1
    assert cs.start(db, patient, user, LanguageCode.EN).session.flow_version == 1

    # And it is still walked under v1: every question it is asked is a v1 one.
    v1 = flow.get_flow(flow.FLOW_ID, 1)
    after = _answer(db, patient, user, started.session.id)
    assert after.question.id in v1.by_id
    assert after.question is v1.question(after.question.id)


# --------------------------------------------------------------------------
# 22–24  attribution, language, provenance
# --------------------------------------------------------------------------


def test_attribution_comes_from_the_question_that_was_asked(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    sid = started.session.id
    _drive_to_end(db, patient, user, sid)
    session = cs.get_own_session(db, patient, sid)

    by_question = {c.response_id: c for c in session.candidates}
    responses = {r.id: r.question_id for r in session.responses}
    attribution = {responses[rid]: c.subject for rid, c in by_question.items()}

    # The question asked about relatives, so its answer is a relative's —
    # regardless of how the answer is worded.
    assert attribution["history.family_conditions"] == FactSubject.FAMILY
    assert attribution["history.conditions"] == FactSubject.SELF
    assert attribution["allergy.which"] == FactSubject.SELF


def test_a_relatives_condition_never_becomes_the_patients_own(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    sid = started.session.id
    _drive_to_end(db, patient, user, sid)
    session = cs.get_own_session(db, patient, sid)

    family = next(
        c for c in session.candidates
        if c.response_id in {r.id for r in session.responses if r.question_id == "history.family_conditions"}
    )
    confirmed = cs.review_candidate(db, patient, user, family.id, "confirm")

    record = db.get(MedicalRecord, confirmed.medical_record_id)
    assert record.type == RecordType.FAMILY_HISTORY
    assert record.type != RecordType.HISTORY_NOTE


def test_the_language_an_answer_was_given_in_is_recorded_with_it(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.TA)

    after = cs.submit_answer(
        db, patient, user, started.session.id, "problem.description", _key(),
        text=TAMIL_COMPLAINT,
    )

    stored = after.session.responses[0]
    assert stored.answer_language == LanguageCode.TA
    assert stored.answer_text == TAMIL_COMPLAINT  # not transliterated, not translated


def test_a_tapped_answer_means_the_same_thing_in_any_language(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.TA)
    sid = started.session.id
    _answer(db, patient, user, sid)
    _answer(db, patient, user, sid)
    _answer(db, patient, user, sid)

    after = cs.submit_answer(
        db, patient, user, sid, "symptom.is_pain", _key(), value={"choices": ["yes"]}
    )

    tapped = next(r for r in after.session.responses if r.question_id == "symptom.is_pain")
    # The option id is stored, not its Tamil label.
    assert tapped.answer_value == {"choices": ["yes"], "bool": True}
    assert tapped.answer_language is None


def test_every_candidate_points_back_at_the_answer_it_came_from(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    sid = started.session.id
    _drive_to_end(db, patient, user, sid)
    session = cs.get_own_session(db, patient, sid)

    response_ids = {r.id for r in session.responses}
    assert session.candidates
    for candidate in session.candidates:
        assert candidate.response_id in response_ids
        assert candidate.session_id == session.id
        assert candidate.patient_id == patient.id


# --------------------------------------------------------------------------
# 25  audit
# --------------------------------------------------------------------------


def test_every_step_of_the_conversation_is_audited(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    sid = started.session.id
    after = _answer(db, patient, user, sid, text="pain in my left knee")
    cs.review_candidate(db, patient, user, after.session.candidates[0].id, "confirm")
    cs.pause(db, patient, user, sid)
    cs.resume(db, patient, user, sid)

    actions = [
        e.action
        for e in db.scalars(
            select(AuditEvent)
            .where(AuditEvent.patient_id == patient.id)
            .order_by(AuditEvent.created_at)
        )
    ]

    for expected in (
        "conversation.session_created",
        "conversation.question_presented",
        "conversation.response_submitted",
        "conversation.candidate_created",
        "conversation.candidate_confirmed",
        "conversation.session_paused",
        "conversation.session_resumed",
    ):
        assert expected in actions


def test_the_audit_trail_carries_ids_and_never_what_the_patient_said(db, actor):
    patient, user = actor
    started = cs.start(db, patient, user, LanguageCode.EN)
    secret = "I have been drinking heavily for years"
    _answer(db, patient, user, started.session.id, text=secret)

    events = db.scalars(
        select(AuditEvent).where(AuditEvent.patient_id == patient.id)
    ).all()

    assert events
    for event in events:
        assert secret not in str(event.details)
