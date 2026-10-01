"""history_general v2 through the service and the database: the A–Z matrix.

The pure tests prove the engine decides correctly. These prove the decisions
are what actually gets stored: which question was asked and why, which were
not asked and why, what a refused request leaves behind (nothing), what a
retry leaves behind (nothing new), and who can reach any of it.

Each test is named for the matrix row it covers. The tree is an engineering
draft awaiting clinical review; nothing here asserts it is clinically right.
"""

import threading
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.conversation import engine
from app.conversation import flow as flows
from app.core.languages import LanguageCode
from app.db.session import SessionLocal
from app.models import (
    AuditEvent,
    ConversationCandidateFact,
    ConversationResponse,
    ConversationSession,
    ConversationSkip,
    MedicalRecord,
    PatientProfile,
)
from app.models.enums import (
    ConversationSection,
    ConversationStatus,
    FactCategory,
    FactReviewState,
    FactSubject,
    RecordType,
    ResponseType,
)
from app.services import conversation_service as cs
from app.services.errors import Conflict, InvalidInput, InvalidTransition, NotFound
from tests.conftest import API, request_consultation

V2 = flows.get_flow("history_general", 2)


@pytest.fixture
def actor(db, make_patient):
    created = make_patient()
    profile = db.get(PatientProfile, uuid.UUID(created.id))
    return profile, profile.user


def _key() -> str:
    return uuid.uuid4().hex


def tap(*choices: str) -> dict:
    return {"value": {"choices": list(choices)}}


def words(text: str) -> dict:
    return {"text": text}


def decline() -> dict:
    return {"declined": True}


def default_for(question_id: str) -> dict:
    """The least committal honest answer to any v2 question."""
    q = V2.question(question_id)
    if q.response_type == ResponseType.FREE_TEXT:
        return words(f"in my own words: {question_id}")
    if q.response_type == ResponseType.DURATION:
        return {"value": {"duration": {"amount": 3, "unit": "days"}}}
    return tap("not_sure")


def answer(db, patient, user, sid, payload: dict | None = None):
    v = cs.view(cs.get_own_session(db, patient, sid))
    qid = v.question.id
    return cs.submit_answer(db, patient, user, sid, qid, _key(), **(payload or default_for(qid)))


def drive(db, patient, user, sid, script: dict[str, dict] | None = None, stop_at: str | None = None):
    """Answer whatever is asked, from `script` where it has an answer, until
    review (or until `stop_at` is the current question)."""
    script = script or {}
    v = cs.view(cs.get_own_session(db, patient, sid))
    for _ in range(40):
        if v.question is None or v.question.id == stop_at:
            return v
        v = cs.submit_answer(db, patient, user, sid, v.question.id, _key(),
                             **script.get(v.question.id, default_for(v.question.id)))
    raise AssertionError("the conversation never reached review")


def asked_in_order(session) -> list[str]:
    return [r.question_id for r in sorted(session.responses, key=lambda r: r.sequence) if r.superseded_at is None]


def live_skips(session) -> dict[str, ConversationSkip]:
    return {s.question_id: s for s in session.skips if s.superseded_at is None}


def snapshot(db, sid) -> tuple:
    """Everything a request could change. Equal before and after = nothing changed."""
    db.expire_all()
    s = db.get(ConversationSession, sid)
    count = lambda model, **kw: db.scalar(select(func.count()).select_from(model).filter_by(**kw))  # noqa: E731
    return (
        s.revision, s.status, s.current_question_id, s.current_question_reason,
        count(ConversationResponse, session_id=sid),
        count(ConversationCandidateFact, session_id=sid),
        count(ConversationSkip, session_id=sid),
        db.scalar(select(func.count()).select_from(AuditEvent)),
        db.scalar(select(func.count()).select_from(MedicalRecord)),
    )


def start(db, patient, user, language=LanguageCode.EN):
    return cs.start(db, patient, user, language).session.id


# --------------------------------------------------------------------------
# A. the normal linear flow
# --------------------------------------------------------------------------


def test_a_a_new_conversation_starts_on_v2_marked_as_a_draft(db, actor):
    patient, user = actor
    v = cs.start(db, patient, user, LanguageCode.EN)
    assert (v.session.flow_id, v.session.flow_version) == ("history_general", 2)
    assert (v.flow.status.value, v.flow.clinical_review.value) == ("engineering_draft", "required")
    assert v.question.id == "current_problem.primary"
    assert v.session.current_question_reason == "flow_sequence"


def test_a_the_linear_path_asks_the_core_questions_and_records_every_skip(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    end = drive(db, patient, user, sid)

    assert end.session.status == ConversationStatus.AWAITING_CONFIRMATION
    assert end.current_step == "review.confirm"
    assert end.session.current_section == ConversationSection.REVIEW
    assert end.session.current_question_reason == "configured_flow_complete"

    core = [q.id for q in V2.questions if q.branch is None]
    assert asked_in_order(end.session) == core
    # Every follow-up was not asked, and each says why — none has an answer.
    skips = live_skips(end.session)
    assert set(skips) == {q.id for q in V2.questions if q.branch}
    assert not set(skips) & set(asked_in_order(end.session))

    done = cs.complete(db, patient, user, sid)
    assert done.session.status == ConversationStatus.COMPLETED


def test_a_every_answer_records_why_its_question_was_asked(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    end = drive(db, patient, user, sid, {"symptom.radiation": tap("yes")})
    reasons = {r.question_id: (r.reason_code, r.trigger_question_id, r.predicate_id)
               for r in end.session.responses}
    assert reasons["current_problem.primary"] == ("flow_sequence", None, None)
    assert reasons["symptom.radiation.location"] == ("radiation_reported", "symptom.radiation", "radiation_is_yes")


# --------------------------------------------------------------------------
# B–L. branches through the real service
# --------------------------------------------------------------------------


def test_b_radiation_yes_asks_where_and_says_why(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    v = drive(db, patient, user, sid, {"symptom.radiation": tap("yes")}, stop_at="symptom.radiation.location")
    assert v.question.id == "symptom.radiation.location"
    assert (v.session.current_question_reason, v.session.current_trigger_question_id) == (
        "radiation_reported", "symptom.radiation")


@pytest.mark.parametrize("said", ["no", "not_sure"])
def test_c_radiation_no_or_not_sure_records_not_asked_and_never_an_answer(db, actor, said):
    patient, user = actor
    sid = start(db, patient, user)
    end = drive(db, patient, user, sid, {"symptom.radiation": tap(said)})
    skip = live_skips(end.session)["symptom.radiation.location"]
    assert (skip.reason_code, skip.trigger_question_id, skip.predicate_id) == (
        "radiation_not_reported", "symptom.radiation", "radiation_is_yes")
    assert "symptom.radiation.location" not in asked_in_order(end.session)
    # What the patient actually said is on their own answer, untouched.
    radiation = next(r for r in end.session.responses if r.question_id == "symptom.radiation")
    assert radiation.answer_value["choices"] == [said]


def test_d_location_other_asks_where_in_their_own_words(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    end = drive(db, patient, user, sid, {"symptom.location": tap("other"),
                                          "symptom.location.other": words("behind my left ear")})
    other = next(r for r in end.session.responses if r.question_id == "symptom.location.other")
    assert other.answer_text == "behind my left ear"
    assert other.reason_code == "location_other_chosen"


def test_e_none_of_these_records_no_symptom_and_no_negative(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    end = drive(db, patient, user, sid, {"symptom.associated": tap("none_of_these")})
    associated = next(r for r in end.session.responses if r.question_id == "symptom.associated")
    assert associated.answer_value == {"choices": ["none_of_these"]}
    # No candidate claims the patient has no other symptoms.
    assert not [c for c in end.session.candidates if c.response_id == associated.id]
    assert live_skips(end.session)["symptom.associated.other"].reason_code == "associated_other_not_chosen"


def test_f_associated_other_asks_and_produces_a_candidate_in_their_words(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    end = drive(db, patient, user, sid, {"symptom.associated": tap("fever", "other"),
                                          "symptom.associated.other": words("tingling in my fingers")})
    other = next(r for r in end.session.responses if r.question_id == "symptom.associated.other")
    candidate = next(c for c in end.session.candidates if c.response_id == other.id)
    assert (candidate.category, candidate.subject, candidate.value) == (
        FactCategory.SYMPTOM, FactSubject.SELF, "tingling in my fingers")
    # The tapped "fever" produced no candidate: it is already the patient's own statement.
    tapped = next(r for r in end.session.responses if r.question_id == "symptom.associated")
    assert not [c for c in end.session.candidates if c.response_id == tapped.id]


def test_g_medications_yes_asks_which_and_confirming_writes_a_record(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    end = drive(db, patient, user, sid, {"medications.current": tap("yes"),
                                          "medications.details": words("metformin 500 twice a day")})
    candidate = next(c for c in end.session.candidates if c.category == FactCategory.MEDICATION)
    assert candidate.review_state == FactReviewState.PENDING
    confirmed = cs.review_candidate(db, patient, user, candidate.id, "confirm")
    record = db.get(MedicalRecord, confirmed.medical_record_id)
    assert (record.type, record.content) == (RecordType.MEDICATION, "metformin 500 twice a day")


def test_h_medications_no_asks_nothing_more_and_writes_nothing(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    end = drive(db, patient, user, sid, {"medications.current": tap("no")})
    assert "medications.details" in live_skips(end.session)
    assert not [c for c in end.session.candidates if c.category == FactCategory.MEDICATION]


def test_i_allergies_yes_asks_what(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    end = drive(db, patient, user, sid, {"allergies.known": tap("yes"), "allergies.details": words("penicillin")})
    candidate = next(c for c in end.session.candidates if c.category == FactCategory.ALLERGY)
    assert candidate.value == "penicillin"


@pytest.mark.parametrize("said", ["no", "not_sure"])
def test_j_allergies_no_or_not_sure_is_never_recorded_as_no_known_allergies(db, actor, said):
    patient, user = actor
    sid = start(db, patient, user)
    end = drive(db, patient, user, sid, {"allergies.known": tap(said)})
    known = next(r for r in end.session.responses if r.question_id == "allergies.known")
    if said == "no":
        assert known.answer_value == {"choices": ["no"], "bool": False}
    else:
        assert known.answer_value == {"choices": ["not_sure"]}  # no `bool` to misread as "no"
    # Nothing is written to the record either way: not an allergy, not "none".
    assert db.scalar(select(func.count()).select_from(MedicalRecord)) == 0
    cs.complete(db, patient, user, sid)
    assert db.scalar(select(func.count()).select_from(MedicalRecord)) == 0


def test_k_several_branches_open_in_one_conversation(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    end = drive(db, patient, user, sid, {
        "symptom.location": tap("other"),
        "symptom.radiation": tap("yes"),
        "symptom.associated": tap("nausea", "other"),
        "history.relevant": tap("yes"),
        "medications.current": tap("yes"),
        "allergies.known": tap("yes"),
    })
    asked = asked_in_order(end.session)
    for follow_up in ("symptom.location.other", "symptom.radiation.location", "symptom.associated.other",
                      "history.relevant.details", "medications.details", "allergies.details"):
        assert follow_up in asked
    assert asked == sorted(asked, key=lambda q: V2.question(q).order)
    # Onset, character, aggravating and relieving were left at "not sure", so
    # exactly their follow-ups were not asked.
    assert set(live_skips(end.session)) == {"symptom.duration", "symptom.character.other",
                                            "symptom.aggravating.other", "symptom.relieving.other"}


def test_l_a_skipped_follow_up_is_listed_in_review_as_not_asked_with_its_reason(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    drive(db, patient, user, sid, {"symptom.onset.when": tap("not_sure")})
    data = cs.review(db, patient, sid)
    item = next(i for i in data.items if i.question.id == "symptom.duration")
    assert (item.outcome, item.response, item.reason_code, item.trigger_question_id) == (
        "not_applicable", None, "onset_not_known", "symptom.onset.when")


def test_l_declining_an_optional_question_is_no_answer_not_not_asked(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    drive(db, patient, user, sid, {"allergies.known": tap("yes"), "allergies.details": decline()})
    data = cs.review(db, patient, sid)
    item = next(i for i in data.items if i.question.id == "allergies.details")
    assert item.outcome == "declined"
    assert item.response.declined and item.response.answer_text is None
    assert not [c for c in data.candidates if c.candidate.response_id == item.response.id]


# --------------------------------------------------------------------------
# M–N. invalid answers change nothing
# --------------------------------------------------------------------------


@pytest.mark.parametrize("payload,code", [
    (tap("kidney"), "invalid_choice"),
    (tap("head", "chest"), "invalid_choice"),
    (words("my head"), "text_not_applicable"),
    ({"value": {"duration": {"amount": 2, "unit": "days"}}}, "value_not_applicable"),
    (decline(), "answer_required"),
])
def test_m_n_an_invalid_answer_is_refused_and_leaves_no_trace(db, actor, payload, code):
    patient, user = actor
    sid = start(db, patient, user)
    drive(db, patient, user, sid, stop_at="symptom.location")
    before = snapshot(db, sid)
    with pytest.raises(InvalidInput) as refused:
        cs.submit_answer(db, patient, user, sid, "symptom.location", _key(), **payload)
    assert refused.value.code == code
    assert snapshot(db, sid) == before


# --------------------------------------------------------------------------
# §31: every invalid transition fails safely and changes nothing
# --------------------------------------------------------------------------


def test_every_invalid_transition_is_refused_without_changing_anything(db, actor, make_patient):
    patient, user = actor
    sid = start(db, patient, user)
    drive(db, patient, user, sid, {"symptom.radiation": tap("no")}, stop_at="symptom.associated")
    stale = cs.get_own_session(db, patient, sid).revision - 1
    other = db.get(PatientProfile, uuid.UUID(make_patient(email="b@example.com").id))
    before = snapshot(db, sid)

    refusals = [
        # a question that is not the current one
        (Conflict, lambda: cs.submit_answer(db, patient, user, sid, "allergies.details", _key(), **words("x"))),
        # a question the engine did not ask
        (Conflict, lambda: cs.submit_answer(db, patient, user, sid, "symptom.radiation.location", _key(),
                                            **words("arm"))),
        (Conflict, lambda: cs.revise_answer(db, patient, user, sid, "symptom.radiation.location", _key(),
                                            **words("arm"))),
        # a question already answered, through the answer route
        (Conflict, lambda: cs.submit_answer(db, patient, user, sid, "symptom.location", _key(), **tap("head"))),
        # a question not yet reached, through the revision route
        (Conflict, lambda: cs.revise_answer(db, patient, user, sid, "allergies.known", _key(), **tap("yes"))),
        # a question from another flow version
        (NotFound, lambda: cs.revise_answer(db, patient, user, sid, "problem.description", _key(), **words("x"))),
        # an answer built against a state that has moved on
        (Conflict, lambda: cs.submit_answer(db, patient, user, sid, "symptom.associated", _key(),
                                            expected_revision=stale, **tap("fever"))),
        # somebody else's conversation
        (NotFound, lambda: cs.submit_answer(db, other, other.user, sid, "symptom.associated", _key(),
                                            **tap("fever"))),
        (NotFound, lambda: cs.review(db, other, sid)),
        # a wrong-shaped answer to the right question
        (InvalidInput, lambda: cs.submit_answer(db, patient, user, sid, "symptom.associated", _key(),
                                                **tap("fever", "none_of_these"))),
    ]
    for error, attempt in refusals:
        with pytest.raises(error):
            attempt()
        assert snapshot(db, sid) == before


def test_a_closed_conversation_takes_no_more_answers_or_changes(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    drive(db, patient, user, sid)
    cs.complete(db, patient, user, sid)
    before = snapshot(db, sid)
    for attempt in (
        lambda: cs.submit_answer(db, patient, user, sid, "current_problem.primary", _key(), **words("again")),
        lambda: cs.revise_answer(db, patient, user, sid, "current_problem.primary", _key(), **words("again")),
        lambda: cs.pause(db, patient, user, sid),
        lambda: cs.resume(db, patient, user, sid),
        lambda: cs.complete(db, patient, user, sid),
    ):
        with pytest.raises((InvalidTransition, Conflict)):
            attempt()
        assert snapshot(db, sid) == before


# --------------------------------------------------------------------------
# O, Z. replays and idempotent retries
# --------------------------------------------------------------------------


def test_o_z_the_same_request_twice_is_one_answer_one_transition_and_one_audit_trail(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    key = _key()
    cs.submit_answer(db, patient, user, sid, "current_problem.primary", key, **words("a stabbing pain"))
    after_first = snapshot(db, sid)

    again = cs.submit_answer(db, patient, user, sid, "current_problem.primary", key, **words("a stabbing pain"))

    # Same revision, same rows, same candidates, and no second audit line.
    assert snapshot(db, sid) == after_first
    assert again.question.id == "symptom.onset.when"


def test_z_retrying_the_last_answer_after_review_began_still_succeeds(db, actor):
    """The final answer moves the conversation into review. A client retrying it
    — because the response was lost on a flaky connection — must get the success
    it already earned, not "this conversation is not waiting for an answer"."""
    patient, user = actor
    sid = start(db, patient, user)
    drive(db, patient, user, sid, stop_at="allergies.known")
    key = _key()
    cs.submit_answer(db, patient, user, sid, "allergies.known", key, **tap("no"))
    assert cs.view(cs.get_own_session(db, patient, sid)).current_step == "review.confirm"
    before = snapshot(db, sid)

    retried = cs.submit_answer(db, patient, user, sid, "allergies.known", key, **tap("no"))

    assert retried.session.status == ConversationStatus.AWAITING_CONFIRMATION
    assert snapshot(db, sid) == before


def test_z_a_request_key_reused_for_a_different_question_is_refused(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    key = _key()
    cs.submit_answer(db, patient, user, sid, "current_problem.primary", key, **words("headache"))
    with pytest.raises(Conflict) as refused:
        cs.submit_answer(db, patient, user, sid, "symptom.onset.when", key, **tap("today"))
    assert refused.value.code == "idempotency_key_reused"


# --------------------------------------------------------------------------
# P–Q. who may reach a conversation
# --------------------------------------------------------------------------


def test_p_another_patient_can_reach_nothing(db, actor, make_patient):
    patient, user = actor
    sid = start(db, patient, user)
    end = drive(db, patient, user, sid, {"allergies.known": tap("yes"), "allergies.details": words("latex")})
    candidate = next(c for c in end.session.candidates if c.category == FactCategory.ALLERGY)
    other = db.get(PatientProfile, uuid.UUID(make_patient(email="b@example.com").id))
    before = snapshot(db, sid)

    for attempt in (
        lambda: cs.get_own_session(db, other, sid),
        lambda: cs.review(db, other, sid),
        lambda: cs.revise_answer(db, other, other.user, sid, "allergies.details", _key(), **words("none")),
        lambda: cs.review_candidate(db, other, other.user, candidate.id, "confirm"),
        lambda: cs.pause(db, other, other.user, sid),
    ):
        with pytest.raises(NotFound):
            attempt()
    assert snapshot(db, sid) == before


def test_q_a_doctor_with_an_authorised_consultation_still_cannot_reach_the_conversation(client, seeded_case):
    case = seeded_case
    consultation = request_consultation(client, case)
    assert consultation.status_code == 201, consultation.text
    session = client.post(f"{API}/patients/me/conversations", json={}, headers=case.patient.h).json()

    for method, url in (
        ("get", f"{API}/patients/me/conversations/current"),
        ("get", f"{API}/patients/me/conversations/{session['id']}"),
        ("get", f"{API}/patients/me/conversations/{session['id']}/review"),
        ("post", f"{API}/patients/me/conversations"),
    ):
        r = getattr(client, method)(url, headers=case.doctor.h, **({"json": {}} if method == "post" else {}))
        assert r.status_code in (403, 404), (url, r.status_code)


def test_q_a_confirmed_conversation_record_reaches_a_doctor_only_when_the_patient_shares_it(
    client, seeded_case, make_doctor
):
    case = seeded_case
    h = case.patient.h
    s = client.post(f"{API}/patients/me/conversations", json={}, headers=h).json()
    while s["question"] is not None:
        q = s["question"]
        body = {"question_id": q["id"], "idempotency_key": _key()}
        if q["id"] == "allergies.known":
            body["value"] = {"choices": ["yes"]}
        elif q["id"] == "allergies.details":
            body["text"] = "sulfa drugs"
        elif q["response_type"] == "free_text":
            body["text"] = "words"
        elif q["response_type"] == "duration":
            body["value"] = {"duration": {"amount": 2, "unit": "days"}}
        else:
            body["value"] = {"choices": ["not_sure"]}
        s = client.post(f"{API}/patients/me/conversations/{s['id']}/answers", json=body, headers=h).json()
    allergy = next(c for c in s["candidates"] if c["category"] == "allergy")
    confirmed = client.post(f"{API}/patients/me/conversations/{s['id']}/candidates/{allergy['id']}",
                            json={"action": "confirm"}, headers=h).json()
    record_id = confirmed["medical_record_id"]

    # Shared nothing from the conversation: the doctor sees no trace of it.
    unshared = request_consultation(client, case).json()
    view = client.get(f"{API}/doctors/me/consultations/{unshared['id']}", headers=case.doctor.h)
    assert view.status_code == 200, view.text
    assert record_id not in view.text and "sulfa" not in view.text

    # Shared with a second doctor: that doctor sees it — through the ordinary
    # sharing mechanism — and the first still does not.
    second = make_doctor(email="arjun@example.com", name="Dr. Arjun Rao")
    shared = request_consultation(client, case, doctor=second, medical_record_ids=[record_id])
    assert shared.status_code == 201, shared.text
    view = client.get(f"{API}/doctors/me/consultations/{shared.json()['id']}", headers=second.h)
    assert view.status_code == 200, view.text
    assert record_id in view.text
    first = client.get(f"{API}/doctors/me/consultations/{unshared['id']}", headers=case.doctor.h)
    assert record_id not in first.text


# --------------------------------------------------------------------------
# R–T. completed, paused, resumed
# --------------------------------------------------------------------------


def test_r_completing_confirms_nothing(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    drive(db, patient, user, sid, {"medications.current": tap("yes"), "allergies.known": tap("yes")})
    done = cs.complete(db, patient, user, sid)
    assert done.session.status == ConversationStatus.COMPLETED
    live = [c for c in done.session.candidates if c.superseded_at is None]
    assert live and all(c.review_state == FactReviewState.PENDING for c in live)
    assert db.scalar(select(func.count()).select_from(MedicalRecord)) == 0


def test_r_candidates_can_still_be_reviewed_after_completion(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    drive(db, patient, user, sid, {"allergies.known": tap("yes"), "allergies.details": words("peanuts")})
    cs.complete(db, patient, user, sid)
    candidate = next(c.candidate for c in cs.review(db, patient, sid).candidates
                     if c.candidate.category == FactCategory.ALLERGY)
    assert cs.review_candidate(db, patient, user, candidate.id, "confirm").medical_record_id is not None


def test_r_the_conversation_cannot_complete_while_questions_remain(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    drive(db, patient, user, sid, stop_at="symptom.radiation")
    with pytest.raises(InvalidTransition):
        cs.complete(db, patient, user, sid)
    assert cs.review(db, patient, sid).view.resolution.next is not None


def test_s_a_paused_conversation_takes_no_answers_and_no_changes(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    drive(db, patient, user, sid, stop_at="symptom.location")
    cs.pause(db, patient, user, sid)
    before = snapshot(db, sid)
    with pytest.raises(InvalidTransition):
        cs.submit_answer(db, patient, user, sid, "symptom.location", _key(), **tap("head"))
    with pytest.raises(InvalidTransition):
        cs.revise_answer(db, patient, user, sid, "current_problem.primary", _key(), **words("changed"))
    assert snapshot(db, sid) == before
    # Reading the review is fine while paused.
    assert cs.review(db, patient, sid).view.session.status == ConversationStatus.PAUSED


def test_t_resuming_returns_to_the_same_question_for_the_same_reason(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    v = drive(db, patient, user, sid, {"symptom.radiation": tap("yes")}, stop_at="symptom.radiation.location")
    reason = (v.session.current_question_reason, v.session.current_trigger_question_id)
    cs.pause(db, patient, user, sid)
    presented_before = db.scalar(select(func.count()).select_from(AuditEvent)
                                 .where(AuditEvent.action == "conversation.question_presented"))

    resumed = cs.resume(db, patient, user, sid)

    assert resumed.question.id == "symptom.radiation.location"
    assert (resumed.session.current_question_reason, resumed.session.current_trigger_question_id) == reason
    # Shown again, not selected again: no second "presented" line.
    assert db.scalar(select(func.count()).select_from(AuditEvent)
                     .where(AuditEvent.action == "conversation.question_presented")) == presented_before


# --------------------------------------------------------------------------
# U. revising an answer
# --------------------------------------------------------------------------


def test_u_revising_keeps_the_old_answer_and_makes_the_new_one_current(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    drive(db, patient, user, sid, {"current_problem.primary": words("headache")}, stop_at="symptom.location")
    v = cs.revise_answer(db, patient, user, sid, "current_problem.primary", _key(),
                         **words("headache and a stiff neck"))

    rows = [r for r in v.session.responses if r.question_id == "current_problem.primary"]
    old, new = sorted(rows, key=lambda r: r.sequence)
    assert (old.answer_text, old.superseded_at is not None) == ("headache", True)
    assert (new.answer_text, new.superseded_at) == ("headache and a stiff neck", None)
    # The candidate follows the answer; the old one is retired, not deleted.
    live = [c for c in v.session.candidates if c.superseded_at is None and c.category == FactCategory.SYMPTOM]
    assert [c.value for c in live] == ["headache and a stiff neck"]
    assert any(c.value == "headache" and c.superseded_at for c in v.session.candidates)
    # The conversation stays where it was.
    assert v.question.id == "symptom.location"


def test_u_a_correction_that_shuts_a_branch_retires_the_follow_up_and_records_why(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    drive(db, patient, user, sid, {"allergies.known": tap("yes"), "allergies.details": words("penicillin")})

    v = cs.revise_answer(db, patient, user, sid, "allergies.known", _key(), **tap("no"))

    details = [r for r in v.session.responses if r.question_id == "allergies.details"]
    assert len(details) == 1 and details[0].superseded_at is not None  # kept, retired
    skip = live_skips(v.session)["allergies.details"]
    assert skip.reason_code == "allergies_not_reported"
    assert not [c for c in v.session.candidates if c.superseded_at is None and c.category == FactCategory.ALLERGY]
    assert v.session.status == ConversationStatus.AWAITING_CONFIRMATION


def test_u_a_correction_that_opens_a_branch_asks_the_follow_up_next(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    end = drive(db, patient, user, sid, {"symptom.radiation": tap("no")})
    assert end.session.status == ConversationStatus.AWAITING_CONFIRMATION
    assert "symptom.radiation.location" in live_skips(end.session)

    v = cs.revise_answer(db, patient, user, sid, "symptom.radiation", _key(), **tap("yes"))

    assert v.session.status == ConversationStatus.AWAITING_ANSWER
    assert v.question.id == "symptom.radiation.location"
    assert v.session.current_question_reason == "radiation_reported"
    # The old "not asked" row is superseded, not deleted, and not current.
    assert "symptom.radiation.location" not in live_skips(v.session)
    assert any(s.question_id == "symptom.radiation.location" and s.superseded_at for s in v.session.skips)


def test_u_an_answer_with_a_confirmed_fact_cannot_be_changed_until_the_fact_is_rejected(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    end = drive(db, patient, user, sid, {"allergies.known": tap("yes"), "allergies.details": words("penicillin")})
    candidate = next(c for c in end.session.candidates if c.category == FactCategory.ALLERGY)
    cs.review_candidate(db, patient, user, candidate.id, "confirm")
    before = snapshot(db, sid)

    for question, payload in (("allergies.details", words("amoxicillin")), ("allergies.known", tap("no"))):
        with pytest.raises(Conflict) as refused:
            cs.revise_answer(db, patient, user, sid, question, _key(), **payload)
        assert refused.value.code == "answer_has_confirmed_facts"
    assert snapshot(db, sid) == before

    cs.review_candidate(db, patient, user, candidate.id, "reject")
    v = cs.revise_answer(db, patient, user, sid, "allergies.details", _key(), **words("amoxicillin"))
    assert [c.value for c in v.session.candidates if c.superseded_at is None and c.category == FactCategory.ALLERGY] == [
        "amoxicillin"]


def test_u_a_superseded_candidate_can_no_longer_be_acted_on(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    end = drive(db, patient, user, sid, {"allergies.known": tap("yes"), "allergies.details": words("penicillin")})
    old = next(c for c in end.session.candidates if c.category == FactCategory.ALLERGY)
    cs.revise_answer(db, patient, user, sid, "allergies.details", _key(), **words("amoxicillin"))
    with pytest.raises(InvalidTransition) as refused:
        cs.review_candidate(db, patient, user, old.id, "confirm")
    assert refused.value.code == "candidate_superseded"


def test_u_revision_is_idempotent_too(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    drive(db, patient, user, sid, stop_at="symptom.location")
    key = _key()
    cs.revise_answer(db, patient, user, sid, "current_problem.primary", key, **words("dizzy"))
    before = snapshot(db, sid)
    cs.revise_answer(db, patient, user, sid, "current_problem.primary", key, **words("dizzy"))
    assert snapshot(db, sid) == before


# --------------------------------------------------------------------------
# V–W. versions through the service
# --------------------------------------------------------------------------


def test_v_a_v1_conversation_is_walked_under_v1_while_new_ones_start_on_v2(db, actor, make_patient):
    patient, user = actor
    old = cs.start(db, patient, user, LanguageCode.EN, flow_version=1)
    assert old.question.id == "problem.description"
    after = cs.submit_answer(db, patient, user, old.session.id, "problem.description", _key(), text="cough")
    assert after.question.id == "symptom.duration"
    assert after.question is flows.get_flow("history_general", 1).question("symptom.duration")

    newcomer = db.get(PatientProfile, uuid.UUID(make_patient(email="new@example.com").id))
    assert cs.start(db, newcomer, newcomer.user, LanguageCode.EN).session.flow_version == 2


def test_w_an_old_answer_resolves_to_the_question_version_the_patient_saw(db, actor):
    patient, user = actor
    old = cs.start(db, patient, user, LanguageCode.EN, flow_version=1)
    sid = old.session.id
    cs.submit_answer(db, patient, user, sid, "problem.description", _key(), text="cough")
    cs.submit_answer(db, patient, user, sid, "symptom.duration", _key(),
                     value={"duration": {"amount": 2, "unit": "weeks"}})
    item = next(i for i in cs.review(db, patient, sid).items if i.question.id == "symptom.duration")
    assert (item.response.question_version, item.question.version) == (1, 1)
    assert item.question.prompt_key == "conversation.q.symptom.duration"
    assert V2.question("symptom.duration").version == 2  # the current wording is different


# --------------------------------------------------------------------------
# X. determinism through the database
# --------------------------------------------------------------------------


def test_x_the_same_answers_produce_the_same_conversation_every_time(db, make_patient):
    script = {"symptom.onset.when": tap("weeks_ago"), "symptom.location": tap("other"),
              "symptom.radiation": tap("yes"), "symptom.associated": tap("dizziness", "other"),
              "medications.current": tap("not_sure"), "allergies.known": tap("yes")}
    traces = []
    for n in range(8):
        profile = db.get(PatientProfile, uuid.UUID(make_patient(email=f"p{n}@example.com").id))
        sid = cs.start(db, profile, profile.user, LanguageCode.TA).session.id
        end = drive(db, profile, profile.user, sid, script)
        traces.append((
            [(r.question_id, r.reason_code, r.trigger_question_id) for r in
             sorted(end.session.responses, key=lambda r: r.sequence)],
            sorted((s.question_id, s.reason_code) for s in live_skips(end.session).values()),
        ))
    assert all(t == traces[0] for t in traces)


# --------------------------------------------------------------------------
# Y. concurrent transitions
# --------------------------------------------------------------------------


def _racing(monkeypatch, competitor):
    """Run `competitor` in its own database session in the middle of the next
    request — after it has read the conversation, before it writes."""
    real = engine.validate
    fired = []

    def validate(*args, **kwargs):
        if not fired:
            fired.append(True)
            other = SessionLocal()
            try:
                competitor(other)
            finally:
                other.close()
        return real(*args, **kwargs)

    monkeypatch.setattr(engine, "validate", validate)


def test_y_two_answers_to_the_same_question_racing_record_only_one(db, actor, monkeypatch):
    patient, user = actor
    sid = start(db, patient, user)
    drive(db, patient, user, sid, stop_at="symptom.location")

    def competitor(other):
        p = other.get(PatientProfile, patient.id)
        cs.submit_answer(other, p, p.user, sid, "symptom.location", _key(), **tap("chest"))

    _racing(monkeypatch, competitor)
    with pytest.raises(Conflict) as lost:
        cs.submit_answer(db, patient, user, sid, "symptom.location", _key(), **tap("head"))
    assert lost.value.code == "conversation_out_of_date"

    session = cs.get_own_session(db, patient, sid)
    location = [r for r in session.responses if r.question_id == "symptom.location"]
    assert [r.answer_value["choices"] for r in location] == [["chest"]]


def test_y_a_race_the_answers_cannot_see_is_caught_by_the_revision(db, actor, monkeypatch):
    """A pause writes no answer, so no unique index can notice it racing an
    answer. The versioned session row does: of two writers that read the same
    revision, only the first can write."""
    patient, user = actor
    sid = start(db, patient, user)
    drive(db, patient, user, sid, stop_at="symptom.location")

    def competitor(other):
        p = other.get(PatientProfile, patient.id)
        cs.pause(other, p, p.user, sid)

    _racing(monkeypatch, competitor)
    with pytest.raises(Conflict) as lost:
        cs.submit_answer(db, patient, user, sid, "symptom.location", _key(), **tap("head"))
    assert lost.value.code == "conversation_out_of_date"

    session = cs.get_own_session(db, patient, sid)
    assert session.status == ConversationStatus.PAUSED
    assert "symptom.location" not in [r.question_id for r in session.responses]


def test_y_a_confirmation_racing_a_revision_of_its_answer_does_not_orphan_a_record(db, actor, monkeypatch):
    patient, user = actor
    sid = start(db, patient, user)
    end = drive(db, patient, user, sid, {"allergies.known": tap("yes"), "allergies.details": words("penicillin")})
    candidate = next(c for c in end.session.candidates if c.category == FactCategory.ALLERGY)

    def competitor(other):
        p = other.get(PatientProfile, patient.id)
        cs.review_candidate(other, p, p.user, candidate.id, "confirm")

    _racing(monkeypatch, competitor)
    with pytest.raises(Conflict):
        cs.revise_answer(db, patient, user, sid, "allergies.details", _key(), **words("amoxicillin"))

    db.expire_all()
    kept = db.get(ConversationCandidateFact, candidate.id)
    assert (kept.review_state, kept.superseded_at) == (FactReviewState.CONFIRMED, None)
    assert db.get(MedicalRecord, kept.medical_record_id) is not None


def test_y_two_starts_at_once_leave_one_open_conversation(db, actor, monkeypatch):
    patient, user = actor
    real = cs.current_session
    calls = []

    def not_yet(db_, patient_):
        # The first check runs before the other request has committed.
        if not calls:
            calls.append(True)
            other = SessionLocal()
            try:
                p = other.get(PatientProfile, patient.id)
                cs.start(other, p, p.user, LanguageCode.EN)
            finally:
                other.close()
            return None
        return real(db_, patient_)

    monkeypatch.setattr(cs, "current_session", not_yet)
    v = cs.start(db, patient, user, LanguageCode.EN)

    open_sessions = db.scalars(select(ConversationSession).where(
        ConversationSession.patient_id == patient.id, ConversationSession.status.in_(cs.OPEN))).all()
    assert [s.id for s in open_sessions] == [v.session.id]


def test_y_the_database_itself_refuses_a_second_open_conversation(db, actor):
    patient, user = actor
    start(db, patient, user)
    db.add(ConversationSession(patient_id=patient.id, flow_id="history_general", flow_version=2))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_y_the_database_itself_refuses_two_current_answers_to_one_question(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    cs.submit_answer(db, patient, user, sid, "current_problem.primary", _key(), **words("headache"))
    db.add(ConversationResponse(
        session_id=sid, patient_id=patient.id, question_id="current_problem.primary", question_version=1,
        section=ConversationSection.CURRENT_PROBLEM, response_type=ResponseType.FREE_TEXT,
        answer_text="a second current answer", answer_value={}, sequence=99, idempotency_key=_key(),
    ))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_y_real_threads_racing_record_exactly_one_answer(actor):
    """The same race as above, with real concurrency rather than an arranged
    interleaving. Whichever thread wins, one answer is recorded and the other
    thread is told."""
    patient, _ = actor
    setup = SessionLocal()
    try:
        p = setup.get(PatientProfile, patient.id)
        sid = cs.start(setup, p, p.user, LanguageCode.EN).session.id
    finally:
        setup.close()

    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def attempt(text: str):
        s = SessionLocal()
        try:
            p = s.get(PatientProfile, patient.id)
            barrier.wait()
            cs.submit_answer(s, p, p.user, sid, "current_problem.primary", _key(), text=text)
            outcomes.append("recorded")
        except Conflict:
            outcomes.append("refused")
        except Exception as exc:  # SQLite may refuse a second writer outright
            outcomes.append(f"refused:{type(exc).__name__}")
        finally:
            s.close()

    threads = [threading.Thread(target=attempt, args=(t,)) for t in ("first", "second")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    check = SessionLocal()
    try:
        rows = check.scalars(select(ConversationResponse).where(
            ConversationResponse.session_id == sid,
            ConversationResponse.question_id == "current_problem.primary")).all()
    finally:
        check.close()
    assert outcomes.count("recorded") == 1 == len(rows), outcomes


# --------------------------------------------------------------------------
# attribution, language, provenance
# --------------------------------------------------------------------------


FATHER = "My father has diabetes, but I have headaches."


def test_attribution_a_mixed_sentence_is_kept_whole_and_invents_no_diabetes_fact(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    v = cs.submit_answer(db, patient, user, sid, "current_problem.primary", _key(), text=FATHER)
    response = v.session.responses[0]
    candidate = v.session.candidates[0]
    assert response.answer_text == FATHER
    # The engine does not read the sentence. The candidate is the sentence, whole,
    # attributed by the question ("what is bothering *you*"), awaiting the patient.
    assert (candidate.value, candidate.subject, candidate.review_state) == (
        FATHER, FactSubject.SELF, FactReviewState.PENDING)
    assert not [c for c in v.session.candidates if c.value.lower() == "diabetes"]

    # Even confirmed, a symptom is not a record (D-025) — and nothing becomes a condition.
    cs.review_candidate(db, patient, user, candidate.id, "confirm")
    records = db.scalars(select(MedicalRecord)).all()
    assert not records
    assert not [r for r in records if r.type == RecordType.CONDITION]


def test_attribution_the_same_sentence_as_history_becomes_a_note_in_their_words_only_if_confirmed(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    end = drive(db, patient, user, sid, {"history.relevant": tap("yes"), "history.relevant.details": words(FATHER)})
    candidate = next(c for c in end.session.candidates if c.category == FactCategory.MEDICAL_HISTORY)
    assert db.scalar(select(func.count()).select_from(MedicalRecord)) == 0  # nothing until confirmed

    record = db.get(MedicalRecord, cs.review_candidate(db, patient, user, candidate.id, "confirm").medical_record_id)
    # A note carrying the whole sentence — "my father" and all — never a "diabetes" condition.
    assert (record.type, record.content) == (RecordType.HISTORY_NOTE, FATHER)
    assert record.title != "diabetes"


def test_a_tap_has_no_language_and_means_the_same_in_tamil_and_english(db, make_patient):
    stored = []
    for n, language in enumerate((LanguageCode.TA, LanguageCode.EN)):
        profile = db.get(PatientProfile, uuid.UUID(make_patient(email=f"l{n}@example.com").id))
        sid = cs.start(db, profile, profile.user, language).session.id
        end = drive(db, profile, profile.user, sid, {"symptom.location": tap("chest")}, stop_at="symptom.character")
        location = next(r for r in end.session.responses if r.question_id == "symptom.location")
        stored.append((location.answer_value, location.answer_language))
    assert stored[0] == stored[1] == ({"choices": ["chest"]}, None)


def test_typed_words_keep_their_language_and_their_exact_form(db, actor):
    patient, user = actor
    sid = cs.start(db, patient, user, LanguageCode.TA).session.id
    tamil = "எனக்கு மூன்று நாட்களாக தலைவலி"
    v = cs.submit_answer(db, patient, user, sid, "current_problem.primary", _key(), text=tamil)
    assert (v.session.responses[0].answer_text, v.session.responses[0].answer_language) == (tamil, LanguageCode.TA)


def test_words_given_for_a_duration_stay_words(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    drive(db, patient, user, sid, {"symptom.onset.when": tap("months_ago")}, stop_at="symptom.duration")
    v = cs.submit_answer(db, patient, user, sid, "symptom.duration", _key(), text="some time ago")
    duration = next(r for r in v.session.responses if r.question_id == "symptom.duration")
    assert (duration.answer_text, duration.answer_value) == ("some time ago", {})
    # And no English "3 days"-style rendering is written anywhere as a candidate.
    assert not [c for c in v.session.candidates if c.response_id == duration.id]


def test_a_long_answer_confirmed_into_a_record_fits_the_title_and_keeps_every_word(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    long_answer = "penicillin and amoxicillin, " * 10  # ~280 characters
    end = drive(db, patient, user, sid, {"allergies.known": tap("yes"), "allergies.details": words(long_answer)})
    candidate = next(c for c in end.session.candidates if c.category == FactCategory.ALLERGY)
    record = db.get(MedicalRecord, cs.review_candidate(db, patient, user, candidate.id, "confirm").medical_record_id)
    assert len(record.title) <= 200
    assert record.content == long_answer.strip()


# --------------------------------------------------------------------------
# review
# --------------------------------------------------------------------------


def test_review_lists_answered_declined_and_not_asked_in_flow_order_and_changes_nothing(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    drive(db, patient, user, sid, {"symptom.radiation": tap("no"), "allergies.known": tap("yes"),
                                    "allergies.details": decline(), "medications.current": tap("yes"),
                                    "medications.details": words("aspirin")})
    before = snapshot(db, sid)
    data = cs.review(db, patient, sid)
    assert snapshot(db, sid) == before

    ids = [i.question.id for i in data.items]
    assert ids == sorted(ids, key=lambda q: V2.question(q).order)
    outcome = {i.question.id: i.outcome for i in data.items}
    assert outcome["symptom.radiation"] == "answered"
    assert outcome["symptom.radiation.location"] == "not_applicable"
    assert outcome["allergies.details"] == "declined"
    medication = next(c for c in data.candidates if c.candidate.category == FactCategory.MEDICATION)
    assert medication.becomes == RecordType.MEDICATION


def test_review_shows_what_a_symptom_candidate_would_become_nothing(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    cs.submit_answer(db, patient, user, sid, "current_problem.primary", _key(), text="chest pain")
    symptom = cs.review(db, patient, sid).candidates[0]
    assert symptom.becomes is None


# --------------------------------------------------------------------------
# audit
# --------------------------------------------------------------------------


def _actions(db, patient_id) -> list[AuditEvent]:
    return db.scalars(select(AuditEvent).where(AuditEvent.patient_id == patient_id)
                      .order_by(AuditEvent.created_at)).all()


def test_every_kind_of_transition_is_audited_with_codes(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    end = drive(db, patient, user, sid, {"symptom.radiation": tap("no"), "allergies.known": tap("yes"),
                                          "allergies.details": words("latex")})
    cs.pause(db, patient, user, sid)
    cs.resume(db, patient, user, sid)
    cs.revise_answer(db, patient, user, sid, "allergies.details", _key(), text="latex gloves")
    allergy = next(c for c in cs.review(db, patient, sid).candidates if c.candidate.category == FactCategory.ALLERGY)
    cs.review_candidate(db, patient, user, allergy.candidate.id, "confirm")
    other = next(c for c in cs.review(db, patient, sid).candidates if c.candidate.category == FactCategory.SYMPTOM)
    cs.review_candidate(db, patient, user, other.candidate.id, "reject")
    cs.complete(db, patient, user, sid)

    events = _actions(db, patient.id)
    actions = {e.action for e in events}
    for expected in (
        "conversation.session_created", "conversation.question_presented", "conversation.response_submitted",
        "conversation.question_not_applicable", "conversation.candidate_created", "conversation.review_reached",
        "conversation.session_paused", "conversation.session_resumed", "conversation.answer_revised",
        "conversation.response_superseded", "conversation.candidate_superseded",
        "conversation.candidate_confirmed", "conversation.candidate_rejected", "conversation.session_completed",
    ):
        assert expected in actions, expected

    skip = next(e for e in events if e.action == "conversation.question_not_applicable"
                and e.details["question_id"] == "symptom.radiation.location")
    assert {
        "reason_code": "radiation_not_reported", "trigger_question_id": "symptom.radiation",
        "transition_type": "not_applicable", "flow_version": 2,
    }.items() <= skip.details.items()
    completed = next(e for e in events if e.action == "conversation.session_completed")
    assert completed.details["outcome"] == "configured_flow_complete"


def test_the_audit_trail_never_carries_what_the_patient_said(db, actor):
    patient, user = actor
    sid = start(db, patient, user)
    secret = "I have been drinking heavily for years"
    drive(db, patient, user, sid, {"current_problem.primary": words(secret),
                                    "history.relevant": tap("yes"), "history.relevant.details": words(secret)})
    for event in _actions(db, patient.id):
        assert secret not in str(event.details)
        # Codes, ids and counts only — no English sentence is logged as a reason.
        for key in ("reason_code", "previous_reason_code"):
            if key in event.details and event.details[key]:
                assert " " not in event.details[key]
