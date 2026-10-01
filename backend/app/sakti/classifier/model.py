"""The vocabulary a classifier tree is written in.

A tree is data: frozen values with stable identifiers, so it can be
fingerprinted, compared and explained without running anything — the pattern
the Phase 5 history flows established (`app.conversation.model`), written here
for a decision tree rather than a question sequence. Nothing is imported from
the healthcare engine: its questions are clinical and it walks a list, while
this walks a tree to one of six categories or to a stop.

Every question offers "unknown", and "unknown" can only lead to a stop. A stop
is not a category and cannot become one.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from functools import cached_property

from app.models.enums import CorpusLane, FormulationCategory

SLUG = re.compile(r"^[a-z][a-z0-9_]*$")
#: Every node offers this choice, and it always stops the walk.
UNKNOWN = "unknown"


@dataclass(frozen=True)
class Choice:
    """One answer to one question. `id` is what is stored; `label_key` what is shown."""

    id: str
    label_key: str


@dataclass(frozen=True)
class Next:
    """Where a choice leads: another question, a category, or a stop. Exactly one."""

    node: str | None = None
    category: FormulationCategory | None = None
    stop: bool = False

    def canonical(self) -> dict:
        if self.stop:
            return {"stop": True}
        if self.category is not None:
            return {"category": self.category.value}
        return {"node": self.node}



@dataclass(frozen=True)
class ReferenceSlot:
    """A legal pointer a node or category rests on — an id, never a citation.

    A curator links the slot to an approved provision version of the slot's
    lane; until then its status is `corpus_required` and nothing is cited.
    The slot's description says what kind of text belongs there, in the
    interface's words; it quotes and paraphrases no law.
    """

    id: str
    lane: CorpusLane
    #: What a curator must find and link, shown to curators.
    describes_key: str

    def canonical(self) -> dict:
        return {"id": self.id, "lane": self.lane.value, "describes_key": self.describes_key}


@dataclass(frozen=True)
class Node:
    """One question, as it stands in one version of one tree."""

    id: str
    #: Localisation keys. Never the text itself.
    question_key: str
    help_key: str
    #: Shown when the answer is "unknown": what is missing, and why it is needed.
    missing_key: str
    why_key: str
    choices: tuple[Choice, ...]
    #: (choice id, where it leads), one per choice.
    transitions: tuple[tuple[str, Next], ...]
    #: Profile fields a user may want in front of them when answering.
    context_fields: tuple[str, ...] = ()
    #: Reference slot ids this question rests on.
    references: tuple[str, ...] = ()

    @cached_property
    def choice_ids(self) -> tuple[str, ...]:
        return tuple(c.id for c in self.choices)

    @cached_property
    def leads(self) -> dict[str, Next]:
        return dict(self.transitions)

    def canonical(self) -> dict:
        return {
            "id": self.id,
            "question_key": self.question_key,
            "help_key": self.help_key,
            "missing_key": self.missing_key,
            "why_key": self.why_key,
            "choices": [{"id": c.id, "label_key": c.label_key} for c in self.choices],
            "transitions": [[choice, nxt.canonical()] for choice, nxt in self.transitions],
            "context_fields": list(self.context_fields),
            "references": list(self.references),
        }


class TreeDefinitionError(ValueError):
    """A tree that cannot be walked honestly. Raised at import, not in front of a user."""


@dataclass(frozen=True)
class Tree:
    classifier_id: str
    version: int
    start: str
    nodes: tuple[Node, ...]
    slots: tuple[ReferenceSlot, ...]
    #: Reference slot ids each category rests on.
    category_references: tuple[tuple[FormulationCategory, tuple[str, ...]], ...] = field(default=())
    #: Engineering draft until a legal reviewer has gone through it (plan Q7).
    status: str = "engineering_draft"
    legal_review: str = "required"

    @cached_property
    def by_id(self) -> dict[str, Node]:
        return {n.id: n for n in self.nodes}

    @cached_property
    def slots_by_id(self) -> dict[str, ReferenceSlot]:
        return {s.id: s for s in self.slots}

    def references_for(self, category: FormulationCategory) -> tuple[str, ...]:
        return dict(self.category_references).get(category, ())

    def canonical(self) -> dict:
        return {
            "classifier_id": self.classifier_id,
            "version": self.version,
            "start": self.start,
            "status": self.status,
            "legal_review": self.legal_review,
            "nodes": [n.canonical() for n in self.nodes],
            "slots": [s.canonical() for s in self.slots],
            "category_references": [[c.value, list(refs)] for c, refs in self.category_references],
        }

    def fingerprint(self) -> str:
        """A hash of everything a classification could depend on.

        Published trees are immutable: any change to a question, choice,
        transition or reference slot changes this, and the pinned value in the
        registry stops it. The fix is a new version, never an edit.
        """
        blob = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def validate(self) -> None:
        problems: list[str] = []
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)):
            problems.append("duplicate node id")
        if self.start not in self.by_id:
            problems.append(f"start {self.start!r} is not a node")
        slot_ids = [s.id for s in self.slots]
        if len(slot_ids) != len(set(slot_ids)):
            problems.append("duplicate reference slot id")

        reached_categories: set[FormulationCategory] = set()
        for node in self.nodes:
            if not SLUG.match(node.id):
                problems.append(f"{node.id!r} is not a slug")
            if len(node.choice_ids) != len(set(node.choice_ids)):
                problems.append(f"{node.id}: duplicate choice id")
            if UNKNOWN not in node.choice_ids:
                problems.append(f"{node.id}: every question must offer {UNKNOWN!r}")
            if set(node.leads) != set(node.choice_ids) or len(node.transitions) != len(node.choices):
                problems.append(f"{node.id}: every choice needs exactly one transition")
            for choice, nxt in node.transitions:
                kinds = sum((nxt.node is not None, nxt.category is not None, nxt.stop))
                if kinds != 1:
                    problems.append(f"{node.id}/{choice}: a transition goes to exactly one place")
                if choice == UNKNOWN and not nxt.stop:
                    problems.append(f"{node.id}: {UNKNOWN!r} must stop the walk")
                if nxt.stop and choice != UNKNOWN:
                    problems.append(f"{node.id}/{choice}: only {UNKNOWN!r} may stop the walk")
                if nxt.node is not None and nxt.node not in self.by_id:
                    problems.append(f"{node.id}/{choice}: leads to unknown node {nxt.node!r}")
                if nxt.category is not None:
                    reached_categories.add(nxt.category)
            for ref in node.references:
                if ref not in self.slots_by_id:
                    problems.append(f"{node.id}: unknown reference slot {ref!r}")

        if reached_categories != set(FormulationCategory):
            missing = sorted(c.value for c in set(FormulationCategory) - reached_categories)
            problems.append(f"categories no answer reaches: {missing}")
        for category, refs in self.category_references:
            for ref in refs:
                if ref not in self.slots_by_id:
                    problems.append(f"{category.value}: unknown reference slot {ref!r}")

        # Every node reachable from the start, and no cycles.
        reachable: set[str] = set()

        def visit(node_id: str, trail: tuple[str, ...]) -> None:
            if node_id in trail:
                problems.append(f"cycle through {node_id}")
                return
            reachable.add(node_id)
            for _, nxt in self.by_id[node_id].transitions:
                if nxt.node is not None and nxt.node in self.by_id:
                    visit(nxt.node, (*trail, node_id))

        if self.start in self.by_id:
            visit(self.start, ())
        unreachable = sorted(set(self.by_id) - reachable)
        if unreachable:
            problems.append(f"unreachable nodes: {unreachable}")

        if problems:
            raise TreeDefinitionError(f"{self.classifier_id} v{self.version}: " + "; ".join(problems))
