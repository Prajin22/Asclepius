"""The deterministic history engine (Phase 5B). Pure functions, no I/O.

Everything that decides what happens next in a conversation lives here, and
nothing here touches a database, a clock, a network or a model. Given the same
flow and the same answers, every function returns the same result — which is
what lets the service, the evaluation harness and the tests all run the same
code and agree.

The service wraps these with persistence, authorization and audit. It does not
make decisions of its own.
"""

import math
from collections.abc import Mapping
from typing import Any

from app.conversation.model import (
    FLOW_COMPLETE,
    FLOW_SEQUENCE,
    TRIGGER_DECLINED,
    TRIGGER_NOT_APPLICABLE,
    Answer,
    FlowDefinition,
    QuestionDefinition,
    QuestionState,
    Resolution,
    Selection,
    Status,
)
from app.models.enums import ResponseType
from app.services.errors import InvalidInput

#: Longest answer accepted. Refused beyond this, never silently shortened:
#: dropping the end of what someone wrote about their health is worse than
#: telling them it was too long.
MAX_ANSWER_CHARS = 2000
#: Longest candidate value. The full answer is always kept beside it.
MAX_VALUE_CHARS = 300

DURATION_UNITS = ("hours", "days", "weeks", "months", "years")
MAX_DURATION_AMOUNT = 1200

CHOICE_TYPES = (ResponseType.YES_NO, ResponseType.SINGLE_CHOICE, ResponseType.MULTI_CHOICE)


# --------------------------------------------------------------------------
# where every question stands
# --------------------------------------------------------------------------


def resolve(flow: FlowDefinition, answers: Mapping[str, Answer]) -> Resolution:
    """Walk the whole flow once, in order, and say where each question stands.

    One pass is enough because a branch's trigger always comes before it (the
    flow refuses to load otherwise), so by the time a question is reached its
    trigger's status is already known. Iteration is over `flow.questions`, an
    ordered tuple; `answers` is only ever looked up, never iterated, so the
    order it was built in cannot change the result.
    """
    states: list[QuestionState] = []
    status_of: dict[str, Status] = {}

    for q in flow.questions:
        answer = answers.get(q.id)

        if q.branch is None:
            applies, reason, trigger, predicate = True, FLOW_SEQUENCE, None, None
        else:
            b = q.branch
            trigger, predicate = b.trigger, b.predicate_id
            trigger_status = status_of[b.trigger]
            if trigger_status == Status.ANSWERED:
                chosen = answers[b.trigger].choices
                if chosen & b.when_chosen:
                    applies, reason = True, b.opened
                else:
                    applies, reason = False, b.closed
            elif trigger_status == Status.DECLINED:
                applies, reason = False, TRIGGER_DECLINED
            elif trigger_status == Status.NOT_APPLICABLE:
                applies, reason = False, TRIGGER_NOT_APPLICABLE
            else:
                # The trigger has not been answered yet, so nobody can know.
                state = QuestionState(q, Status.UNDETERMINED, None, trigger, predicate, answer is not None)
                states.append(state)
                status_of[q.id] = Status.UNDETERMINED
                continue

        if not applies:
            status = Status.NOT_APPLICABLE
        elif answer is None:
            status = Status.OPEN
        elif answer.declined:
            status = Status.DECLINED
        else:
            status = Status.ANSWERED

        states.append(
            QuestionState(
                q, status, reason, trigger, predicate,
                stale_answer=(status == Status.NOT_APPLICABLE and answer is not None),
            )
        )
        status_of[q.id] = status

    return Resolution(flow, tuple(states))


def select(resolution: Resolution) -> Selection:
    """The next question: the first open one, in flow order."""
    state = resolution.next
    if state is None:
        return Selection(None, FLOW_COMPLETE)
    return Selection(state.question, state.reason_code, state.trigger_question_id, state.predicate_id)


def next_question(flow: FlowDefinition, answers: Mapping[str, Answer]) -> Selection:
    return select(resolve(flow, answers))


def plan_revision(
    flow: FlowDefinition, answers: Mapping[str, Answer], question_id: str, replacement: Answer
) -> tuple[Resolution, tuple[QuestionState, ...]]:
    """What changing one answer would do, before anything changes.

    Returns the resolution under the new answer and every *other* answered
    question that would stop applying — including ones that stop applying
    because something they depended on stopped applying. Those answers are not
    wrong; they answered a question that, given the correction, would not have
    been asked. The caller retires them rather than deleting them.
    """
    revised = dict(answers)
    revised[question_id] = replacement
    resolution = resolve(flow, revised)
    invalidated = tuple(s for s in resolution.stale if s.question.id != question_id)
    return resolution, invalidated


# --------------------------------------------------------------------------
# what a valid answer looks like
# --------------------------------------------------------------------------


def _reject(message: str, code: str) -> None:
    raise InvalidInput(message, code=code)


def validate(
    definition: QuestionDefinition,
    text: str | None,
    value: Mapping[str, Any] | None,
    declined: bool,
) -> tuple[str | None, dict[str, Any]]:
    """Check an answer against the question's declared shape.

    Returns `(answer_text, answer_value)` exactly as they will be stored. The
    server decides what a valid answer is; each response type accepts one shape
    and nothing else, so a client cannot widen a single choice into three,
    attach prose to a tap, or answer a yes/no with a duration.
    """
    value = dict(value or {})
    choices = value.get("choices")
    duration = value.get("duration")
    unknown_fields = set(value) - {"choices", "duration"}
    if unknown_fields:
        _reject("That answer has fields this question does not take", "value_not_applicable")

    cleaned = (text or "").strip()
    if len(cleaned) > MAX_ANSWER_CHARS:
        _reject("That answer is longer than this question accepts", "answer_too_long")

    if declined:
        if definition.required:
            _reject("This question needs an answer", "answer_required")
        if cleaned or choices or duration:
            _reject("A declined question cannot also carry an answer", "declined_with_answer")
        return None, {}

    kind = definition.response_type

    if kind == ResponseType.FREE_TEXT:
        if choices is not None or duration is not None:
            _reject("This question takes words, not a choice", "value_not_applicable")
        if not cleaned:
            _reject("An answer is needed", "answer_required")
        # The patient's own words, exactly. Nothing normalises or translates them.
        return cleaned, {}

    if kind in CHOICE_TYPES:
        if cleaned:
            # Words belong in the follow-up question that asks for them.
            _reject("This question takes a choice, not words", "text_not_applicable")
        if duration is not None:
            _reject("This question takes a choice, not a duration", "value_not_applicable")
        if not isinstance(choices, list) or not choices:
            _reject("Choose one of the offered answers", "invalid_choice")
        allowed = definition.option_ids
        if any(c not in allowed for c in choices):
            _reject("Choose from the offered answers", "invalid_choice")
        unique = set(choices)

        if kind in (ResponseType.YES_NO, ResponseType.SINGLE_CHOICE):
            if len(unique) != 1:
                _reject("Choose exactly one answer", "invalid_choice")
            (choice,) = unique
            stored: dict[str, Any] = {"choices": [choice]}
            # `bool` is set only for a plain yes or no. "Not sure" is neither,
            # and recording it as False would make it read as "no".
            if kind == ResponseType.YES_NO and choice in ("yes", "no"):
                stored["bool"] = choice == "yes"
            return None, stored

        exclusive = {o.id for o in definition.options if o.exclusive}
        if unique & exclusive and len(unique) > 1:
            _reject("That choice cannot be combined with others", "exclusive_choice_combined")
        # Stored in the question's own order, so the same taps in a different
        # order are the same stored answer.
        return None, {"choices": [o for o in allowed if o in unique]}

    if kind == ResponseType.DURATION:
        if choices is not None:
            _reject("This question takes a length of time", "value_not_applicable")
        stored = {}
        if duration is not None:
            if not isinstance(duration, Mapping) or set(duration) - {"amount", "unit"}:
                _reject("A duration is an amount and a unit", "invalid_duration")
            amount, unit = duration.get("amount"), duration.get("unit")
            if (
                isinstance(amount, bool)
                or not isinstance(amount, (int, float))
                or not math.isfinite(amount)
                or amount <= 0
                or amount > MAX_DURATION_AMOUNT
            ):
                _reject("How long should be a positive number", "invalid_duration")
            if unit not in DURATION_UNITS:
                _reject("Choose a unit of time", "invalid_duration")
            stored = {"duration": {"amount": amount, "unit": unit}}
        if not stored and not cleaned:
            _reject("An answer is needed", "answer_required")
        # Words are kept as words. "Some time ago" stays "some time ago", and
        # "three days" typed out is not turned into a number here: a structured
        # duration exists only when the patient gave one.
        return cleaned or None, stored

    _reject("Unsupported response type", "unsupported_response_type")
    raise AssertionError("unreachable")


def answer_of(declined: bool, answer_value: Mapping[str, Any]) -> Answer:
    """The engine's view of a stored answer: the controlled part only."""
    if declined:
        return Answer(declined=True)
    return Answer(choices=frozenset(answer_value.get("choices") or ()))


def candidate_value(definition: QuestionDefinition, answer_text: str | None, declined: bool) -> str | None:
    """What an answer would contribute if the patient confirms it — or nothing.

    Only a free-text answer to a question with a category produces a
    candidate, and its value is the patient's own words. A tapped option or a
    structured duration is already exactly what the patient said, in a
    controlled form; restating it as a candidate would mean writing an English
    rendering ("3 days", "nausea") into their record, which is the defect D-065
    exists to prevent.
    """
    if declined or definition.category is None or definition.response_type != ResponseType.FREE_TEXT:
        return None
    return (answer_text or "").strip()[:MAX_VALUE_CHARS] or None
