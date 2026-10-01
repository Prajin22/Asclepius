"""The conversation evaluation harness, and proof that it can fail.

A hard gate that reads 0 is only worth something if it can read more than 0.
Each test below breaks the engine in one specific way and asserts the gate
built to catch that breakage trips — so a clean run means the engine behaved,
not that the harness was looking the other way.
"""

import random

from app.conversation import engine
from app.conversation.model import QuestionState, Resolution, Status
from evaluation.run_conversation_eval import GATES, load, run


def _gates(**kwargs) -> dict:
    return run(repeat=3, **kwargs)["hard_gates"]


def test_the_real_engine_passes_every_path_with_every_gate_at_zero():
    result = run(repeat=10)
    assert result["failed"] == []
    assert result["passed"] == result["paths"] == len(load())
    assert result["hard_gates"] == {g: 0 for g in GATES}


def test_every_v2_branch_is_both_opened_and_shut_by_some_path():
    cov = run(repeat=1)["branch_coverage_v2"]
    assert cov["opened"] == cov["shut"] == cov["branches"] == 10


def test_every_matrix_row_the_harness_can_check_has_a_path():
    assert {"A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "V", "attribution"} <= set(
        run(repeat=1)["by_matrix"])


def test_the_harness_reports_the_flows_as_drafts():
    status = run(repeat=1)["flow_status"]
    assert all(s == "engineering_draft, clinical review required" for s in status.values())


# --------------------------------------------------------------------------
# break the engine, watch the gate trip
# --------------------------------------------------------------------------


def test_an_engine_that_ignores_branches_trips_wrong_question_and_fake_answer(monkeypatch):
    real = engine.resolve

    def every_branch_open(flow, answers):
        r = real(flow, answers)
        forced = tuple(
            QuestionState(s.question, Status.ANSWERED if s.question.id in answers else Status.OPEN,
                          s.reason_code or "forced", s.trigger_question_id, s.predicate_id)
            if s.status in (Status.NOT_APPLICABLE, Status.UNDETERMINED) else s
            for s in r.states
        )
        return Resolution(flow, forced)

    monkeypatch.setattr(engine, "resolve", every_branch_open)
    gates = _gates()
    assert gates["wrong_question"] > 0
    assert gates["fake_answer"] > 0


def test_storing_not_sure_as_false_trips_collapsed_negative(monkeypatch):
    real = engine.validate

    def collapsing(definition, text, value, declined):
        answer_text, stored = real(definition, text, value, declined)
        if stored.get("choices") and set(stored["choices"]) & {"not_sure", "unsure"}:
            stored = stored | {"bool": False}
        return answer_text, stored

    monkeypatch.setattr(engine, "validate", collapsing)
    assert _gates()["collapsed_negative"] > 0


def test_candidates_made_from_taps_trip_invented_fact(monkeypatch):
    real = engine.candidate_value

    def inventing(definition, answer_text, declined):
        if definition.options and not declined:
            return "no other symptoms"
        return real(definition, answer_text, declined)

    monkeypatch.setattr(engine, "candidate_value", inventing)
    assert _gates()["invented_fact"] > 0


def test_a_validator_that_accepts_anything_trips_accepted_invalid(monkeypatch):
    monkeypatch.setattr(engine, "validate", lambda d, t, v, dec: (t, dict(v or {})))
    assert _gates(paths=[p for p in load() if "invalid" in p])["accepted_invalid"] > 0


def test_an_engine_that_depends_on_chance_trips_nondeterminism(monkeypatch):
    real = engine.next_question
    rng = random.Random(1)

    def moody(flow, answers):
        selection = real(flow, answers)
        if selection.question is not None and rng.random() < 0.5:
            return type(selection)(selection.question, "some_other_reason",
                                   selection.trigger_question_id, selection.predicate_id)
        return selection

    monkeypatch.setattr(engine, "next_question", moody)
    assert _gates()["nondeterminism"] > 0


def test_a_wrong_expectation_fails_the_path_that_holds_it():
    paths = load()
    broken = next(p for p in paths if p["id"] == "C-radiation-no")
    broken = broken | {"expect": broken["expect"] | {"not_applicable": {"symptom.radiation.location": "radiation_absent"}}}
    result = run(repeat=1, paths=[broken])
    assert result["passed"] == 0
    assert "radiation_absent" in result["failed"][0]["failures"][0]


def test_a_refusal_for_the_wrong_reason_fails_the_path():
    paths = [p for p in load() if p["id"] == "M-option-not-offered"]
    paths = [paths[0] | {"invalid": paths[0]["invalid"] | {"code": "answer_required"}}]
    result = run(repeat=1, paths=paths)
    assert result["passed"] == 0

