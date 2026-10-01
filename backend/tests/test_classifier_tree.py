"""The formulation classifier as data and as a walk (IP-SAKTI Phase 3, D-087–D-089).

No database, no API, no provider: the tree and the engine are pure, so every
branch the build brief specifies is checked here directly, and so is every
place "unknown" can be answered.
"""

import itertools
import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.core.config import REPO_ROOT
from app.models.enums import CorpusLane, FormulationCategory
from app.sakti.classifier import engine, registry
from app.sakti.classifier.model import UNKNOWN, Next, TreeDefinitionError
from app.sakti.classifier.trees import formulation_v1

TREE = formulation_v1.TREE
C = FormulationCategory
THERAPEUTIC = {"purpose": "therapeutic"}

# --------------------------------------------------------------------------
# The tree as data
# --------------------------------------------------------------------------


def test_the_current_tree_loads_and_is_version_1_of_the_formulation_classifier():
    tree = registry.current_tree()
    assert (tree.classifier_id, tree.version) == ("ip_sakti_formulation", 1)
    assert tree.start == "purpose"
    assert [n.id for n in tree.nodes] == ["purpose", "classical_formula", "schedule_combination", "phytopharmaceutical"]


def test_published_trees_are_never_edited_in_place():
    for key, tree in registry.TREES.items():
        assert tree.fingerprint() == registry.PUBLISHED[key], (
            f"{key} changed after it was published. Add a new version instead of editing this one."
        )


def test_the_fingerprint_sees_every_change():
    renamed = replace(TREE, nodes=(replace(TREE.nodes[0], question_key="classifier.v1.other"), *TREE.nodes[1:]))
    assert renamed.fingerprint() != TREE.fingerprint()


def test_the_categories_are_exactly_the_six_specified():
    assert {c.value for c in FormulationCategory} == {
        "classical", "patent_proprietary", "new_or_non_classical", "phytopharmaceutical", "ayurveda_aahara", "cosmetic",
    }


def test_node_ids_are_unique_and_every_transition_lands_somewhere_real():
    ids = [n.id for n in TREE.nodes]
    assert len(ids) == len(set(ids))
    for node in TREE.nodes:
        assert set(node.leads) == set(node.choice_ids)
        for nxt in node.leads.values():
            assert (nxt.node in TREE.by_id) or nxt.category is not None or nxt.stop


def test_every_question_offers_unknown_and_unknown_only_ever_stops():
    for node in TREE.nodes:
        assert UNKNOWN in node.choice_ids
        assert node.leads[UNKNOWN] == Next(stop=True)
        assert all(not nxt.stop for choice, nxt in node.transitions if choice != UNKNOWN)


def test_every_reference_slot_is_in_the_india_lane_and_names_no_text():
    assert {s.lane for s in TREE.slots} == {CorpusLane.INDIA}
    for slot in TREE.slots:
        assert slot.describes_key.startswith("classifier.v1.slot.")
    for node in TREE.nodes:
        assert set(node.references) <= set(TREE.slots_by_id)


@pytest.mark.parametrize("broken,problem", [
    (lambda t: replace(t, nodes=(*t.nodes, t.nodes[0])), "duplicate node id"),
    (lambda t: replace(t, start="nowhere"), "start"),
    (lambda t: replace(t, nodes=(replace(t.nodes[0], transitions=(("therapeutic", Next(node="classical_formula")),
                                                                    ("nutrition", Next(category=C.AYURVEDA_AAHARA)),
                                                                    ("external_beautification", Next(category=C.COSMETIC)),
                                                                    (UNKNOWN, Next(category=C.CLASSICAL)))),
                                 *t.nodes[1:])), "must stop"),
    (lambda t: replace(t, nodes=(replace(t.nodes[0], transitions=(("therapeutic", Next(stop=True)),
                                                                    ("nutrition", Next(category=C.AYURVEDA_AAHARA)),
                                                                    ("external_beautification", Next(category=C.COSMETIC)),
                                                                    (UNKNOWN, Next(stop=True)))),
                                 *t.nodes[1:])), "only 'unknown' may stop"),
    (lambda t: replace(t, nodes=t.nodes[:3]), "categories no answer reaches"),
    (lambda t: replace(t, nodes=(*t.nodes[:3], replace(t.nodes[3], transitions=(
        ("yes", Next(node="purpose")), ("no", Next(category=C.NEW_OR_NON_CLASSICAL)), (UNKNOWN, Next(stop=True)))))),
     "cycle"),
])
def test_a_malformed_tree_is_refused_before_anyone_sees_it(broken, problem):
    with pytest.raises(TreeDefinitionError, match=problem):
        broken(TREE).validate()


def test_a_question_nothing_leads_to_is_refused():
    orphan = replace(TREE.nodes[3], id="orphan")
    with pytest.raises(TreeDefinitionError, match="unreachable"):
        replace(TREE, nodes=(*TREE.nodes, orphan)).validate()


def test_an_unknown_version_is_not_substituted():
    with pytest.raises(registry.UnknownTree):
        registry.get_tree(99)


def test_every_key_the_tree_uses_is_translated_in_all_three_languages():
    keys = set()
    for node in TREE.nodes:
        keys |= {node.question_key, node.help_key, node.missing_key, node.why_key}
        keys |= {c.label_key for c in node.choices}
    keys |= {s.describes_key for s in TREE.slots}
    keys |= {f"classifier.category.{c.value}" for c in FormulationCategory}

    def lookup(catalog: dict, key: str):
        node = catalog
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node if isinstance(node, str) else None

    for locale in ("en", "hi", "ta"):
        path = Path(REPO_ROOT) / "packages" / "i18n" / "messages" / f"sakti.{locale}.json"
        catalog = json.loads(path.read_text(encoding="utf-8"))
        missing = sorted(k for k in keys if not lookup(catalog, k))
        assert missing == [], f"{locale} lacks {missing}"


# --------------------------------------------------------------------------
# The walk: every specified branch
# --------------------------------------------------------------------------


@pytest.mark.parametrize("answers,category", [
    ({"purpose": "nutrition"}, C.AYURVEDA_AAHARA),
    ({"purpose": "external_beautification"}, C.COSMETIC),
    ({**THERAPEUTIC, "classical_formula": "yes"}, C.CLASSICAL),
    ({**THERAPEUTIC, "classical_formula": "no", "schedule_combination": "yes"}, C.PATENT_PROPRIETARY),
    ({**THERAPEUTIC, "classical_formula": "no", "schedule_combination": "no", "phytopharmaceutical": "yes"},
     C.PHYTOPHARMACEUTICAL),
    ({**THERAPEUTIC, "classical_formula": "no", "schedule_combination": "no", "phytopharmaceutical": "no"},
     C.NEW_OR_NON_CLASSICAL),
])
def test_each_specified_branch_reaches_its_category(answers, category):
    walk = engine.walk(TREE, answers)
    assert (walk.state, walk.category, walk.node_id) == ("determined", category, None)
    assert [s.node_id for s in walk.path] == list(answers)


@pytest.mark.parametrize("answers,next_question", [
    ({}, "purpose"),
    (THERAPEUTIC, "classical_formula"),
    ({**THERAPEUTIC, "classical_formula": "no"}, "schedule_combination"),
    ({**THERAPEUTIC, "classical_formula": "no", "schedule_combination": "no"}, "phytopharmaceutical"),
])
def test_each_question_leads_to_the_next_specified_one(answers, next_question):
    walk = engine.walk(TREE, answers)
    assert (walk.state, walk.node_id, walk.category) == ("ask", next_question, None)


@pytest.mark.parametrize("answers,stopped_at", [
    ({"purpose": UNKNOWN}, "purpose"),
    ({**THERAPEUTIC, "classical_formula": UNKNOWN}, "classical_formula"),
    ({**THERAPEUTIC, "classical_formula": "no", "schedule_combination": UNKNOWN}, "schedule_combination"),
    ({**THERAPEUTIC, "classical_formula": "no", "schedule_combination": "no", "phytopharmaceutical": UNKNOWN},
     "phytopharmaceutical"),
])
def test_unknown_stops_exactly_where_it_is_given_and_yields_no_category(answers, stopped_at):
    walk = engine.walk(TREE, answers)
    assert (walk.state, walk.node_id, walk.category) == ("stopped", stopped_at, None)


def test_no_combination_of_answers_with_an_unknown_on_its_path_yields_a_category():
    choices = {n.id: n.choice_ids for n in TREE.nodes}
    for combo in itertools.product(*choices.values()):
        walk = engine.walk(TREE, dict(zip(choices, combo, strict=True)))
        if any(step.choice == UNKNOWN for step in walk.path):
            assert walk.state == "stopped" and walk.category is None
        else:
            assert walk.state == "determined" and walk.category in FormulationCategory


def test_every_category_is_reachable_and_nothing_else_is():
    choices = {n.id: n.choice_ids for n in TREE.nodes}
    reached = {engine.walk(TREE, dict(zip(choices, combo, strict=True))).category
               for combo in itertools.product(*choices.values())}
    assert reached - {None} == set(FormulationCategory)


def test_questions_the_walk_does_not_reach_are_not_asked_and_are_reported_off_the_path():
    walk = engine.walk(TREE, {"purpose": "nutrition", "classical_formula": "yes", "phytopharmaceutical": "yes"})
    assert walk.category == C.AYURVEDA_AAHARA
    assert [s.node_id for s in walk.path] == ["purpose"]
    assert walk.off_path == ("classical_formula", "phytopharmaceutical")


def test_the_same_answers_always_give_the_same_result():
    answers = {**THERAPEUTIC, "classical_formula": "no", "schedule_combination": "yes"}
    walks = {engine.walk(TREE, dict(answers)) for _ in range(20)}
    assert len(walks) == 1
    walk = walks.pop()
    assert engine.answers_sha256(walk.path) == engine.answers_sha256(engine.walk(TREE, answers).path)


def test_an_answer_that_is_not_a_choice_is_refused_never_coerced():
    with pytest.raises(engine.InvalidChoice):
        engine.walk(TREE, {"purpose": "probably therapeutic"})
    with pytest.raises(engine.InvalidChoice):
        engine.walk(TREE, {"made_up_question": "yes"})


def test_a_result_rests_on_the_reference_slots_of_its_path_and_category():
    walk = engine.walk(TREE, {**THERAPEUTIC, "classical_formula": "yes"})
    refs = walk.references(TREE)
    assert "first_schedule" in refs and "category_classical" in refs
    assert "category_phytopharmaceutical" not in refs  # never on this path
    assert len(refs) == len(set(refs))


def test_the_engine_imports_no_model_client_clock_or_database():
    source = Path(engine.__file__).read_text(encoding="utf-8")
    for forbidden in ("providers.ai", "anthropic", "openai", "httpx", "sqlalchemy", "datetime", "random"):
        assert forbidden not in source, forbidden
