"""Invariants of the history engine, checked over many seeded random walks.

The matrix tests pick paths by hand. These let a seeded random generator pick
thousands — every answer valid, every branch reachable — and check after every
single step that ten properties still hold. The seeds are fixed, so a failure is
reproducible, and the walks are deterministic, so the suite is too.

The strongest check is the reconciliation invariant: after every transition,
what is persisted (current answers, "not asked" rows, the current question and
its reason) must equal what the pure engine derives from the answers alone.
If the service ever made a decision the engine did not, this is where it shows.

    1  the next question always belongs to the session's own flow version
    2  a question that was not asked never has a current answer
    3  nothing advances a session except an accepted answer to its current question
    4  a candidate never becomes confirmed without the confirmation operation
    5  a completed session accepts no new answers
    6  another patient's request never becomes part of the conversation
    7  the same answers give the same transitions
    8  a retry never duplicates anything
    9  question ids do not change with the language
    10 stored choices are option ids, never labels
"""

import random
import uuid

import pytest
from sqlalchemy import func, select

from app.conversation import engine
from app.conversation import flow as flows
from app.conversation.model import Answer, QuestionDefinition, Status
from app.core.languages import LanguageCode
from app.models import (
    AuditEvent,
    ConversationCandidateFact,
    ConversationResponse,
    ConversationSession,
    ConversationSkip,
    MedicalRecord,
    PatientProfile,
)
from app.models.enums import ConversationStatus, FactReviewState, ResponseType
from app.services import conversation_service as cs
from app.services.errors import Conflict, InvalidTransition, NotFound

V2 = flows.get_flow("history_general", 2)
PHRASES = ("a dull ache", "it comes and goes", "worse at night", "penicillin", "metformin",
           "some time ago", "tingling", "behind my eye", "தலைவலி", "सिरदर्द")


def random_answer(rng: random.Random, q: QuestionDefinition) -> dict:
    """Any valid answer to `q` — including declining when that is allowed."""
    if not q.required and rng.random() < 0.15:
        return {"declined": True}
    if q.response_type == ResponseType.FREE_TEXT:
        return {"text": rng.choice(PHRASES)}
    if q.response_type == ResponseType.DURATION:
        if rng.random() < 0.3:
            return {"text": rng.choice(("some time ago", "a while", "three days"))}
        return {"value": {"duration": {"amount": rng.randint(1, 30),
                                       "unit": rng.choice(("hours", "days", "weeks", "months", "years"))}}}
    if q.response_type in (ResponseType.YES_NO, ResponseType.SINGLE_CHOICE):
        return {"value": {"choices": [rng.choice(q.option_ids)]}}
    exclusive = [o.id for o in q.options if o.exclusive]
    ordinary = [o.id for o in q.options if not o.exclusive]
    if exclusive and rng.random() < 0.3:
        return {"value": {"choices": [rng.choice(exclusive)]}}
    return {"value": {"choices": rng.sample(ordinary, rng.randint(1, min(3, len(ordinary))))}}


def engine_answer(q: QuestionDefinition, payload: dict) -> Answer:
    text, value = engine.validate(q, payload.get("text"), payload.get("value"), payload.get("declined", False))
    return engine.answer_of(payload.get("declined", False), value)


# --------------------------------------------------------------------------
# pure: thousands of walks through the engine alone
# --------------------------------------------------------------------------


@pytest.mark.parametrize("flow_version", [1, 2])
def test_pure_walks_always_terminate_ask_each_question_once_and_repeat_exactly(flow_version):
    f = flows.get_flow("history_general", flow_version)
    for seed in range(1500):
        rng = random.Random(seed)
        answers: dict[str, Answer] = {}
        trace = []
        for _ in range(len(f.questions) + 1):
            selection = engine.next_question(f, answers)
            if selection.question is None:
                break
            q = selection.question
            # 1: it is this flow's own question, not one from another version.
            assert f.question(q.id) is q
            # never re-asks an answered question, never asks a not-applicable one
            assert q.id not in answers
            state = engine.resolve(f, answers).by_id[q.id]
            assert state.status == Status.OPEN
            answers[q.id] = engine_answer(q, random_answer(rng, q))
            trace.append((q.id, selection.reason_code, selection.trigger_question_id))
        else:
            pytest.fail(f"seed {seed}: the walk did not terminate")

        final = engine.resolve(f, answers)
        assert final.next is None
        # 2: nothing answered is not applicable; every question is resolved.
        assert not final.stale
        assert all(s.status in (Status.ANSWERED, Status.DECLINED, Status.NOT_APPLICABLE) for s in final.states)
        # 7: replaying the same answers gives the same transitions, step by step.
        replay, given = [], {}
        for qid, reason, trigger in trace:
            selection = engine.next_question(f, given)
            replay.append((selection.question.id, selection.reason_code, selection.trigger_question_id))
            given[qid] = answers[qid]
        assert replay == trace


def test_pure_revisions_always_leave_a_consistent_resolution():
    for seed in range(1500):
        rng = random.Random(10_000 + seed)
        answers: dict[str, Answer] = {}
        while (selection := engine.next_question(V2, answers)).question is not None:
            q = selection.question
            answers[q.id] = engine_answer(q, random_answer(rng, q))

        for _ in range(5):
            target = rng.choice(sorted(answers))
            q = V2.question(target)
            replacement = engine_answer(q, random_answer(rng, q))
            _, invalidated = engine.plan_revision(V2, answers, target, replacement)
            retired = {s.question.id for s in invalidated}
            for state in invalidated:
                assert state.status == Status.NOT_APPLICABLE and state.question.id != target

            # Apply it as the service does: replace the answer, retire the invalidated.
            answers = {k: v for k, v in answers.items() if k not in retired}
            answers[target] = replacement
            after = engine.resolve(V2, answers)
            assert not after.stale
            assert after.by_id[target].status in (Status.ANSWERED, Status.DECLINED)

            # Answer whatever the correction opened, so the next revision starts complete.
            while (selection := engine.next_question(V2, answers)).question is not None:
                nq = selection.question
                answers[nq.id] = engine_answer(nq, random_answer(rng, nq))


# --------------------------------------------------------------------------
# through the service: persisted state always equals derived state
# --------------------------------------------------------------------------


def _key() -> str:
    return uuid.uuid4().hex


def _snapshot(db, sid) -> tuple:
    db.expire_all()
    s = db.get(ConversationSession, sid)
    count = lambda m: db.scalar(select(func.count()).select_from(m).filter_by(session_id=sid))  # noqa: E731
    return (s.revision, s.status, s.current_question_id,
            count(ConversationResponse), count(ConversationCandidateFact), count(ConversationSkip),
            db.scalar(select(func.count()).select_from(AuditEvent)),
            db.scalar(select(func.count()).select_from(MedicalRecord)))


def assert_reconciled(db, patient, sid) -> None:
    """Persisted state is exactly what the engine derives from the answers."""
    session = cs.get_own_session(db, patient, sid)
    f = cs.flow_of(session)
    current = {r.question_id: r for r in session.responses if r.superseded_at is None}
    skips = {s.question_id: s for s in session.skips if s.superseded_at is None}
    resolution = engine.resolve(f, {q: engine.answer_of(r.declined, r.answer_value) for q, r in current.items()})

    # 1: every stored question belongs to the session's flow, at the version stored.
    for r in session.responses:
        assert f.question(r.question_id) is not None
        assert f.question(r.question_id).version == r.question_version
    # 2: no current answer for a question that was not asked; skips are exactly the engine's.
    assert not set(current) & set(skips)
    assert {q: s.reason_code for q, s in skips.items()} == {
        s.question.id: s.reason_code for s in resolution.not_applicable}
    assert not resolution.stale
    # The current question and its reason are the engine's, never the service's own.
    selection = engine.select(resolution)
    if session.status == ConversationStatus.AWAITING_ANSWER:
        assert (session.current_question_id, session.current_question_reason,
                session.current_trigger_question_id) == (
            selection.question.id, selection.reason_code, selection.trigger_question_id)
    if session.status in (ConversationStatus.AWAITING_CONFIRMATION, ConversationStatus.COMPLETED):
        assert selection.question is None
    # 4: nothing in these walks confirms anything, so nothing is confirmed.
    assert all(c.review_state == FactReviewState.PENDING for c in session.candidates)
    assert db.scalar(select(func.count()).select_from(MedicalRecord)) == 0
    # 10: every stored choice is one of the question's option ids.
    for r in session.responses:
        for choice in (r.answer_value or {}).get("choices", []):
            assert choice in f.question(r.question_id).option_ids
            assert "." not in choice  # never a label key


def _walk(db, patient, user, intruder, seed: int, language: LanguageCode) -> list[tuple]:
    rng = random.Random(seed)
    sid = cs.start(db, patient, user, language).session.id
    trace = []
    for _ in range(60):
        v = cs.view(cs.get_own_session(db, patient, sid))
        if v.question is None:
            break
        q = v.question
        payload = random_answer(rng, q)
        key = _key()

        # 6: another patient's attempt changes nothing and joins nothing.
        before = _snapshot(db, sid)
        with pytest.raises(NotFound):
            cs.submit_answer(db, intruder, intruder.user, sid, q.id, _key(), **payload)
        assert _snapshot(db, sid) == before

        # Read before answering: the view holds the live session, which the
        # answer moves on to the next question.
        asked_because = v.session.current_question_reason
        cs.submit_answer(db, patient, user, sid, q.id, key, **payload)
        trace.append((q.id, asked_because))
        assert_reconciled(db, patient, sid)

        # 8: the same request again changes nothing at all.
        after = _snapshot(db, sid)
        cs.submit_answer(db, patient, user, sid, q.id, key, **payload)
        assert _snapshot(db, sid) == after

        # 3: answering something other than the current question moves nothing.
        stale_target = rng.choice([x.id for x in V2.questions])
        now = cs.view(cs.get_own_session(db, patient, sid))
        if now.question is not None and stale_target != now.question.id:
            before = _snapshot(db, sid)
            with pytest.raises((Conflict, InvalidTransition)):
                cs.submit_answer(db, patient, user, sid, stale_target, _key(), **random_answer(rng, V2.question(stale_target)))
            assert _snapshot(db, sid) == before

        # Now and then, change an earlier answer, and check everything again.
        if rng.random() < 0.25:
            answered = [r.question_id for r in cs.get_own_session(db, patient, sid).responses if r.superseded_at is None]
            target = rng.choice(answered)
            cs.revise_answer(db, patient, user, sid, target, _key(), **random_answer(rng, V2.question(target)))
            assert_reconciled(db, patient, sid)

    cs.complete(db, patient, user, sid)
    assert_reconciled(db, patient, sid)
    # 5: a completed session takes nothing more.
    before = _snapshot(db, sid)
    with pytest.raises(InvalidTransition):
        cs.submit_answer(db, patient, user, sid, "current_problem.primary", _key(), text="one more thing")
    assert _snapshot(db, sid) == before
    return trace


def test_service_walks_keep_every_invariant(db, make_patient):
    intruder = db.get(PatientProfile, uuid.UUID(make_patient(email="intruder@example.com").id))
    for seed in range(12):
        profile = db.get(PatientProfile, uuid.UUID(make_patient(email=f"walker{seed}@example.com").id))
        _walk(db, profile, profile.user, intruder, seed, LanguageCode.EN)


def test_the_same_script_in_two_languages_asks_the_same_questions(db, make_patient):
    """9: question ids and transitions do not depend on the language answered in."""
    intruder = db.get(PatientProfile, uuid.UUID(make_patient(email="intruder@example.com").id))
    traces = []
    for n, language in enumerate((LanguageCode.EN, LanguageCode.TA, LanguageCode.HI)):
        profile = db.get(PatientProfile, uuid.UUID(make_patient(email=f"lang{n}@example.com").id))
        traces.append(_walk(db, profile, profile.user, intruder, seed=77, language=language))
    assert traces[0] == traces[1] == traces[2]
