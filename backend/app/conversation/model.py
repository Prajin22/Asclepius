"""The vocabulary a history flow is written in (Phase 5B).

A flow is data. Every question, every option and every branch is a frozen
value with a stable identifier, so a flow can be fingerprinted, compared, and
explained without running anything. In particular a branch is *declared* — "ask
this when that question's answer includes one of these options" — rather than
written as a function, because a function cannot be inspected, and "why was I
asked this?" must always have an answer that does not depend on reading code.

Nothing here is clinical knowledge. A branch chooses the next *question*. It
never draws a conclusion from an answer, and no answer is evidence of anything
beyond what the patient said.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from functools import cached_property

from app.models.enums import ConversationSection, FactCategory, FactSubject, ResponseType

#: Option ids, predicate ids and reason codes: lower-case, stable, never prose.
SLUG = re.compile(r"^[a-z][a-z0-9_]*$")


class FlowStatus(StrEnum):
    """How far a flow is from being something anyone should rely on."""

    #: Written by engineers as a reasonable structure. Not reviewed by a
    #: clinician, not validated, not complete. Every flow is this today.
    ENGINEERING_DRAFT = "engineering_draft"


class ClinicalReview(StrEnum):
    #: A clinician must go through the flow question by question before it is
    #: used with real people.
    REQUIRED = "required"


# ---- engine-level reason codes ------------------------------------------
#
# Branch-specific codes live on each `Branch`. These are the ones the engine
# itself produces. All of them are machine-readable and rendered in the browser
# from `conversation.reason.<code>`; none is ever an English sentence.

#: An unconditional question, reached in configured order.
FLOW_SEQUENCE = "flow_sequence"
#: Every applicable question has been resolved; the review step is next.
#: Deliberately not "history complete": the configured flow ended, nothing more.
FLOW_COMPLETE = "configured_flow_complete"
#: The question this one depends on was declined, so nobody knows whether it
#: applies — and "not asked" must not be recorded as though it were "no".
TRIGGER_DECLINED = "trigger_declined"
#: The question this one depends on was itself not applicable.
TRIGGER_NOT_APPLICABLE = "trigger_not_applicable"

ENGINE_REASON_CODES = frozenset({FLOW_SEQUENCE, FLOW_COMPLETE, TRIGGER_DECLINED, TRIGGER_NOT_APPLICABLE})

#: The review step's identifier. It is a step, not a question: confirmation is
#: an action on candidates, so no response type is invented to model it.
REVIEW_STEP_ID = "review.confirm"


@dataclass(frozen=True)
class Option:
    """One tap-to-answer choice.

    `id` is what is stored; `label_key` is what is rendered. A stored answer
    therefore means the same thing in every language, and translating a label
    never changes what a patient is recorded as having chosen.
    """

    id: str
    label_key: str
    #: Cannot be combined with any other choice. "None of these", "not sure"
    #: and "nothing noticed" are each a complete answer on their own; ticking
    #: "fever" and "none of these" together says nothing coherent.
    exclusive: bool = False


@dataclass(frozen=True)
class Branch:
    """When a question applies, stated as data.

    The question applies when the answer to `trigger` includes any option in
    `when_chosen`. Only an explicit, controlled answer can open a branch; free
    text is never read for meaning to decide what to ask.
    """

    #: Names the condition, e.g. `radiation_is_yes`. Stable across wording.
    predicate_id: str
    #: The question whose answer decides this one. Must come earlier.
    trigger: str
    when_chosen: frozenset[str]
    #: Reason code when the branch opens, e.g. `radiation_reported`.
    opened: str
    #: Reason code when the trigger was answered and the branch stayed shut,
    #: e.g. `radiation_not_reported`. Worded so that it is true whether the
    #: patient said "no" or "not sure" — the difference lives in their answer,
    #: and the skip must not quietly claim the stronger of the two.
    closed: str


@dataclass(frozen=True)
class QuestionDefinition:
    """One question, as it stood in one version of one flow."""

    id: str
    version: int
    #: Position in the flow. Explicit numbers, not list position, so that a
    #: follow-up has a visible insertion point (radiation 60, its detail 65) and
    #: nothing depends on the order anything happened to be written or stored.
    order: int
    section: ConversationSection
    response_type: ResponseType
    #: Localisation key. Never the text itself.
    prompt_key: str
    options: tuple[Option, ...] = ()
    required: bool = True
    #: What a confirmed free-text answer contributes to, when it maps to one of
    #: the Phase 2 categories. `None` means the answer is context, not a fact.
    category: FactCategory | None = None
    #: Whose health the answer describes — from what was asked, never inferred
    #: from how it was answered (D-062).
    subject: FactSubject = FactSubject.SELF
    #: `None` means always asked.
    branch: Branch | None = None
    help_key: str | None = None

    @property
    def option_ids(self) -> tuple[str, ...]:
        return tuple(o.id for o in self.options)

    def canonical(self) -> dict:
        return {
            "id": self.id,
            "version": self.version,
            "order": self.order,
            "section": self.section.value,
            "response_type": self.response_type.value,
            "prompt_key": self.prompt_key,
            "help_key": self.help_key,
            "required": self.required,
            "category": self.category.value if self.category else None,
            "subject": self.subject.value,
            "options": [[o.id, o.label_key, o.exclusive] for o in self.options],
            "branch": None
            if self.branch is None
            else {
                "predicate_id": self.branch.predicate_id,
                "trigger": self.branch.trigger,
                "when_chosen": sorted(self.branch.when_chosen),
                "opened": self.branch.opened,
                "closed": self.branch.closed,
            },
        }


class FlowDefinitionError(ValueError):
    """A flow that cannot be walked honestly. Raised at import, not at runtime."""


@dataclass(frozen=True)
class FlowDefinition:
    flow_id: str
    version: int
    questions: tuple[QuestionDefinition, ...]
    status: FlowStatus = FlowStatus.ENGINEERING_DRAFT
    clinical_review: ClinicalReview = ClinicalReview.REQUIRED

    @cached_property
    def by_id(self) -> dict[str, QuestionDefinition]:
        return {q.id: q for q in self.questions}

    def question(self, question_id: str) -> QuestionDefinition | None:
        return self.by_id.get(question_id)

    def canonical(self) -> dict:
        return {
            "flow_id": self.flow_id,
            "version": self.version,
            "status": self.status.value,
            "clinical_review": self.clinical_review.value,
            "questions": [q.canonical() for q in self.questions],
        }

    def fingerprint(self) -> str:
        """A hash of everything a patient's answers could depend on.

        Published flows are immutable. A change to any question, option or
        branch changes this value, and the test that pins it fails — the fix is
        a new flow version, never an edit to one already in use.
        """
        blob = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def reason_codes(self) -> frozenset[str]:
        codes = set(ENGINE_REASON_CODES)
        for q in self.questions:
            if q.branch:
                codes.update((q.branch.opened, q.branch.closed))
        return frozenset(codes)

    def validate(self) -> None:
        """Structural checks. A flow that fails any of these cannot be walked
        deterministically, so it fails loudly at import rather than quietly in
        front of a patient."""
        problems: list[str] = []
        seen_ids: set[str] = set()
        seen_orders: set[int] = set()
        previous_order = None
        position: dict[str, int] = {}

        for index, q in enumerate(self.questions):
            if q.id in seen_ids:
                problems.append(f"{q.id}: duplicate question id")
            seen_ids.add(q.id)
            if q.order in seen_orders:
                problems.append(f"{q.id}: duplicate order {q.order}")
            seen_orders.add(q.order)
            if previous_order is not None and q.order <= previous_order:
                problems.append(f"{q.id}: order {q.order} is not after {previous_order}")
            previous_order = q.order
            position[q.id] = index

            choice_type = q.response_type in (
                ResponseType.YES_NO, ResponseType.SINGLE_CHOICE, ResponseType.MULTI_CHOICE
            )
            if choice_type and not q.options:
                problems.append(f"{q.id}: a choice question needs options")
            if not choice_type and q.options:
                problems.append(f"{q.id}: only choice questions carry options")

            option_ids = [o.id for o in q.options]
            if len(option_ids) != len(set(option_ids)):
                problems.append(f"{q.id}: duplicate option id")
            for o in q.options:
                if not SLUG.match(o.id):
                    problems.append(f"{q.id}: option id {o.id!r} is not a slug")
                if o.exclusive and q.response_type != ResponseType.MULTI_CHOICE:
                    problems.append(f"{q.id}: 'exclusive' only means something on a multi-choice question")

            if q.branch:
                b = q.branch
                for code in (b.predicate_id, b.opened, b.closed):
                    if not SLUG.match(code):
                        problems.append(f"{q.id}: {code!r} is not a slug")
                if b.trigger not in position:
                    problems.append(f"{q.id}: trigger {b.trigger} does not come before it in this flow")
                else:
                    trigger = self.questions[position[b.trigger]]
                    unknown = set(b.when_chosen) - set(trigger.option_ids)
                    if unknown:
                        problems.append(f"{q.id}: branch names options {sorted(unknown)} that {b.trigger} does not offer")
                    if not b.when_chosen:
                        problems.append(f"{q.id}: a branch that no answer can open")

        if problems:
            raise FlowDefinitionError(f"{self.flow_id} v{self.version}: " + "; ".join(problems))


# ---- the engine's view of a session -------------------------------------


@dataclass(frozen=True)
class Answer:
    """What the engine is allowed to know about one current answer.

    Deliberately only the controlled part. The engine never sees the patient's
    words, so it cannot branch on them even by accident.
    """

    declined: bool = False
    choices: frozenset[str] = field(default_factory=frozenset)


class Status(StrEnum):
    """Where one question stands, given the answers so far."""

    ANSWERED = "answered"
    #: The patient chose not to answer an optional question. "No answer."
    DECLINED = "declined"
    #: The engine did not ask, because the branch did not open. "Not asked."
    NOT_APPLICABLE = "not_applicable"
    #: Applies, and has not been answered yet.
    OPEN = "open"
    #: Cannot be known yet: the question it depends on has not been answered.
    UNDETERMINED = "undetermined"


@dataclass(frozen=True)
class QuestionState:
    question: QuestionDefinition
    status: Status
    #: Why it is asked (answered / declined / open) or why it is not
    #: (not_applicable). `None` only while undetermined.
    reason_code: str | None
    trigger_question_id: str | None = None
    predicate_id: str | None = None
    #: An answer is on record for a question that no longer applies. Only a
    #: revised answer upstream can cause this, and revision resolves it.
    stale_answer: bool = False


@dataclass(frozen=True)
class Resolution:
    """Every question in the flow, and where it stands. Ordered as the flow is."""

    flow: FlowDefinition
    states: tuple[QuestionState, ...]

    @cached_property
    def by_id(self) -> dict[str, QuestionState]:
        return {s.question.id: s for s in self.states}

    @property
    def next(self) -> QuestionState | None:
        return next((s for s in self.states if s.status == Status.OPEN), None)

    @property
    def not_applicable(self) -> tuple[QuestionState, ...]:
        return tuple(s for s in self.states if s.status == Status.NOT_APPLICABLE)

    @property
    def stale(self) -> tuple[QuestionState, ...]:
        return tuple(s for s in self.states if s.stale_answer)

    @property
    def remaining(self) -> int:
        """Applicable questions still unanswered. Follow-ups whose trigger is
        not yet answered are not counted, so this is a floor, never a promise."""
        return sum(1 for s in self.states if s.status == Status.OPEN)


@dataclass(frozen=True)
class Selection:
    """The next question and exactly why — or, when there is none, why not."""

    question: QuestionDefinition | None
    reason_code: str
    trigger_question_id: str | None = None
    predicate_id: str | None = None
