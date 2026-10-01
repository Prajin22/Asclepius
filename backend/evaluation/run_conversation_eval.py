"""Replay the conversation evaluation paths through the deterministic engine.

    uv run python -m evaluation.run_conversation_eval
    uv run python -m evaluation.run_conversation_eval --repeat 50

No provider, no network, no database: the engine is pure, so this runs the
exact code the service runs, on hand-written paths whose expectations were
worked out from the flow definition rather than from the engine.

It measures whether the engine walks each flow as written. It says nothing
about whether a flow is clinically right — every flow is an engineering draft
awaiting clinical review.

Six results are pass/fail rather than a count, and each must be 0:

    WRONG QUESTION      a step asked something other than the path expects
    FAKE ANSWER         a question the path says was not asked got an answer
    COLLAPSED NEGATIVE  "not sure" was stored with a yes/no value
    INVENTED FACT       a candidate came from a tap or a duration, not the patient's words
    ACCEPTED INVALID    an answer the question does not take was accepted
    NONDETERMINISM      the same path gave a different result on a repeat

If any is non-zero the phase is not finished, whatever the other numbers say.
"""

import argparse
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.conversation import engine
from app.conversation import flow as flows
from app.conversation.model import FlowDefinition, QuestionDefinition
from app.models.enums import ResponseType
from app.services.errors import InvalidInput

DATASET = Path(__file__).resolve().parent / "conversation_paths.json"
RESULTS = Path(__file__).resolve().parent / "results"

GATES = ("wrong_question", "fake_answer", "collapsed_negative", "invented_fact", "accepted_invalid", "nondeterminism")
UNSURE = ("not_sure", "unsure")


@dataclass
class Trace:
    asked: list[str] = field(default_factory=list)
    reasons: dict[str, list] = field(default_factory=dict)
    declined: list[str] = field(default_factory=list)
    stored: dict[str, dict] = field(default_factory=dict)
    stored_text: dict[str, str | None] = field(default_factory=dict)
    candidates: dict[str, str] = field(default_factory=dict)
    not_applicable: dict[str, str] = field(default_factory=dict)

    def key(self) -> str:
        return json.dumps(self.__dict__, sort_keys=True, ensure_ascii=False)


@dataclass
class PathResult:
    id: str
    matrix: str
    flow_version: int
    passed: bool
    failures: list[str]
    gates: Counter
    trace: Trace | None = None


def load(path: Path = DATASET) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["paths"]


def default_answer(q: QuestionDefinition) -> dict:
    """The least committal honest answer; keeps every branch shut."""
    if q.response_type == ResponseType.FREE_TEXT:
        return {"text": "in my own words"}
    if q.response_type == ResponseType.DURATION:
        return {"value": {"duration": {"amount": 3, "unit": "days"}}}
    for way_out in UNSURE:
        if way_out in q.option_ids:
            return {"value": {"choices": [way_out]}}
    return {"value": {"choices": [q.option_ids[-1]]}}


def trace_path(f: FlowDefinition, given: dict[str, dict]) -> Trace:
    """Walk one flow, answering from `given` where it has an answer."""
    t, answers = Trace(), {}
    for _ in range(len(f.questions) + 1):
        selection = engine.next_question(f, answers)
        if selection.question is None:
            break
        q = selection.question
        spec = given.get(q.id, default_answer(q))
        declined = bool(spec.get("declined", False))
        text, value = engine.validate(q, spec.get("text"), spec.get("value"), declined)
        t.asked.append(q.id)
        t.reasons[q.id] = [selection.reason_code, selection.trigger_question_id]
        if declined:
            t.declined.append(q.id)
        t.stored[q.id] = value
        t.stored_text[q.id] = text
        candidate = engine.candidate_value(q, text, declined)
        if candidate is not None:
            t.candidates[q.id] = candidate
        answers[q.id] = engine.answer_of(declined, value)
    else:
        raise RuntimeError("the walk did not terminate")
    t.not_applicable = {s.question.id: s.reason_code for s in engine.resolve(f, answers).not_applicable}
    return t


def _gates_from(f: FlowDefinition, t: Trace) -> Counter:
    """The checks that need no expectations at all."""
    gates = Counter()
    for qid, value in t.stored.items():
        choices = value.get("choices") or []
        if any(c in UNSURE for c in choices) and "bool" in value:
            gates["collapsed_negative"] += 1
    for qid in t.candidates:
        if f.question(qid).response_type != ResponseType.FREE_TEXT:
            gates["invented_fact"] += 1
    return gates


def run_path(path: dict, repeat: int = 5) -> PathResult:
    f = flows.get_flow("history_general", path["flow_version"])
    failures: list[str] = []
    gates: Counter = Counter()

    if "invalid" in path:
        spec = path["invalid"]
        q = f.question(spec["question"])
        answer = spec["answer"]
        try:
            engine.validate(q, answer.get("text"), answer.get("value"), bool(answer.get("declined", False)))
        except InvalidInput as refused:
            if refused.code != spec["code"]:
                failures.append(f"refused as {refused.code}, expected {spec['code']}")
        else:
            gates["accepted_invalid"] += 1
            failures.append("an invalid answer was accepted")
        return PathResult(path["id"], path["matrix"], path["flow_version"], not failures and not gates, failures, gates)

    t = trace_path(f, path.get("answers", {}))
    expect = path.get("expect", {})

    if "asked" in expect:
        wanted = expect["asked"]
        wrong = sum(1 for a, b in zip(t.asked, wanted) if a != b) + abs(len(t.asked) - len(wanted))
        if wrong:
            gates["wrong_question"] += wrong
            failures.append(f"asked {t.asked}, expected {wanted}")

    for qid, code in expect.get("not_applicable", {}).items():
        if qid in t.asked:
            gates["fake_answer"] += 1
            failures.append(f"{qid} should not have been asked, and was answered")
        elif t.not_applicable.get(qid) != code:
            failures.append(f"{qid} not asked because {t.not_applicable.get(qid)!r}, expected {code!r}")

    for qid, (code, trigger) in expect.get("reasons", {}).items():
        if t.reasons.get(qid) != [code, trigger]:
            failures.append(f"{qid} asked because {t.reasons.get(qid)}, expected {[code, trigger]}")

    for qid, value in expect.get("stored", {}).items():
        if t.stored.get(qid) != value:
            failures.append(f"{qid} stored {t.stored.get(qid)}, expected {value}")
    for qid, text in expect.get("stored_text", {}).items():
        if t.stored_text.get(qid) != text:
            failures.append(f"{qid} stored text {t.stored_text.get(qid)!r}, expected {text!r}")

    if "declined" in expect and sorted(t.declined) != sorted(expect["declined"]):
        failures.append(f"declined {t.declined}, expected {expect['declined']}")
    if "candidates" in expect and sorted(t.candidates) != sorted(expect["candidates"]):
        failures.append(f"candidates from {sorted(t.candidates)}, expected {sorted(expect['candidates'])}")
    for qid, value in expect.get("candidate_values", {}).items():
        if t.candidates.get(qid) != value:
            failures.append(f"candidate from {qid} is {t.candidates.get(qid)!r}, expected {value!r}")

    gates.update(_gates_from(f, t))
    first = t.key()
    if any(trace_path(f, path.get("answers", {})).key() != first for _ in range(repeat)):
        gates["nondeterminism"] += 1
        failures.append("the same path gave a different result on a repeat")

    return PathResult(path["id"], path["matrix"], path["flow_version"], not failures and not gates, failures, gates, t)


def coverage(results: list[PathResult], flow_version: int = 2) -> dict[str, dict[str, bool]]:
    """For every branch in a flow: did some path open it, and did some path shut it?"""
    f = flows.get_flow("history_general", flow_version)
    walked = [r.trace for r in results if r.trace is not None and r.flow_version == flow_version]
    return {
        q.id: {
            "opened": any(q.id in t.asked for t in walked),
            "shut": any(q.id in t.not_applicable for t in walked),
        }
        for q in f.questions
        if q.branch
    }


def report(results: list[PathResult]) -> dict[str, Any]:
    gates = Counter()
    for r in results:
        gates.update(r.gates)
    cov = coverage(results)
    return {
        "flow_status": {f"v{f.version}": f"{f.status.value}, clinical review {f.clinical_review.value}"
                        for f in flows.FLOWS.values()},
        "paths": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": [{"id": r.id, "failures": r.failures} for r in results if not r.passed],
        "hard_gates": {g: gates.get(g, 0) for g in GATES},
        "branch_coverage_v2": {
            "branches": len(cov),
            "opened": sum(1 for c in cov.values() if c["opened"]),
            "shut": sum(1 for c in cov.values() if c["shut"]),
            "detail": cov,
        },
        "by_matrix": dict(sorted(Counter(r.matrix for r in results).items())),
    }


def run(repeat: int = 5, paths: list[dict] | None = None) -> dict[str, Any]:
    return report([run_path(p, repeat) for p in (paths if paths is not None else load())])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repeat", type=int, default=5, help="replays per path for the determinism gate")
    parser.add_argument("--out", type=Path, default=RESULTS / "conversation-paths.json")
    args = parser.parse_args()

    result = run(args.repeat)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"paths {result['passed']}/{result['paths']} passed")
    for failure in result["failed"]:
        print(f"  FAILED {failure['id']}: {'; '.join(failure['failures'])}")
    cov = result["branch_coverage_v2"]
    print(f"v2 branches: {cov['opened']}/{cov['branches']} opened, {cov['shut']}/{cov['branches']} shut")
    print("hard gates (each must be 0):")
    for gate, count in result["hard_gates"].items():
        print(f"  {gate.replace('_', ' ').upper():<20} {count}")
    print(f"written to {args.out}")
    if any(result["hard_gates"].values()) or result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
