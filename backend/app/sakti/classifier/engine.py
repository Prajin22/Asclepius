"""The walk: a tree and some answers in; a question, a stop or a category out.

Pure — no database, no clock, no network, no model. Given the same tree and the
same answers it always returns the same thing, which is what makes a
classification reproducible years later from its stored tree version and
answers.

The walk starts at the tree's start and follows each answered question's
transition. It ends at the first question without an answer (ask it), at an
"unknown" (stop there: the information is missing, and nothing is guessed), or
at a category. Answers to questions the walk never reaches are ignored and
reported as off the path, so a caller can retire them.
"""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass

from app.models.enums import FormulationCategory
from app.sakti.classifier.model import Tree


class InvalidChoice(ValueError):
    """An answer that is not one of the question's choices. Never coerced into one."""


@dataclass(frozen=True)
class Step:
    node_id: str
    choice: str


@dataclass(frozen=True)
class Walk:
    #: The answered questions the walk passed through, in order.
    path: tuple[Step, ...]
    #: "ask" | "stopped" | "determined"
    state: str
    #: The question to ask ("ask"), or the question answered "unknown" ("stopped").
    node_id: str | None = None
    category: FormulationCategory | None = None
    #: Answered questions the walk did not reach.
    off_path: tuple[str, ...] = ()

    def references(self, tree: Tree) -> tuple[str, ...]:
        """The reference slots this walk rests on, in order, without repeats."""
        refs: list[str] = []
        for step in self.path:
            refs.extend(tree.by_id[step.node_id].references)
        if self.category is not None:
            refs.extend(tree.references_for(self.category))
        return tuple(dict.fromkeys(refs))


def walk(tree: Tree, answers: Mapping[str, str]) -> Walk:
    for node_id, choice in answers.items():
        node = tree.by_id.get(node_id)
        if node is None:
            raise InvalidChoice(f"{node_id!r} is not a question in {tree.classifier_id} v{tree.version}")
        if choice not in node.choice_ids:
            raise InvalidChoice(f"{choice!r} is not a choice for {node_id!r}")

    path: list[Step] = []
    node_id = tree.start
    while True:
        node = tree.by_id[node_id]
        choice = answers.get(node_id)
        if choice is None:
            result = Walk(tuple(path), "ask", node_id=node_id)
            break
        path.append(Step(node_id, choice))
        nxt = node.leads[choice]
        if nxt.stop:
            result = Walk(tuple(path), "stopped", node_id=node_id)
            break
        if nxt.category is not None:
            result = Walk(tuple(path), "determined", category=nxt.category)
            break
        node_id = nxt.node  # validated: the tree has no cycles
    on_path = {s.node_id for s in result.path}
    off = tuple(sorted(n for n in answers if n not in on_path))
    return Walk(result.path, result.state, result.node_id, result.category, off)


def answers_sha256(path: tuple[Step, ...]) -> str:
    """A fingerprint of the answers a result rests on, in path order."""
    blob = json.dumps([[s.node_id, s.choice] for s in path], separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
