"""ip_sakti_formulation v1 — the build brief's decision tree, as data (D-088).

    Q1 purpose:       nutrition → AYURVEDA_AAHARA
                      external beautification → COSMETIC
                      therapeutic → Q2
    Q2 classical:     yes → CLASSICAL                no → Q3
    Q3 schedule:      yes → PATENT_PROPRIETARY       no → Q4
    Q4 phyto:         yes → PHYTOPHARMACEUTICAL      no → NEW_OR_NON_CLASSICAL
    any question:     unknown → stop (no category)

The questions' wording lives in the catalogue under `classifier.v1.*`; this
module holds only keys. Each reference slot names the kind of official text a
node or category rests on, never the text itself: none is linked yet, because
the corpus holds no approved official source, so every one starts as
`corpus_required`.

Engineering draft. A legal reviewer must go through it before anyone relies on
it (plan Q7).
"""

from app.models.enums import CorpusLane, FormulationCategory
from app.sakti.classifier.model import UNKNOWN, Choice, Next, Node, ReferenceSlot, Tree

C = FormulationCategory
_V = "classifier.v1"


def _choices(*ids: str) -> tuple[Choice, ...]:
    return tuple(Choice(i, f"classifier.choice.{i}") for i in (*ids, UNKNOWN))


def _keys(node: str) -> dict[str, str]:
    return {
        "question_key": f"{_V}.{node}.question",
        "help_key": f"{_V}.{node}.help",
        "missing_key": f"{_V}.{node}.missing",
        "why_key": f"{_V}.{node}.why",
    }


_STOP = Next(stop=True)

TREE = Tree(
    classifier_id="ip_sakti_formulation",
    version=1,
    start="purpose",
    nodes=(
        Node(
            id="purpose",
            **_keys("purpose"),
            choices=_choices("therapeutic", "nutrition", "external_beautification"),
            transitions=(
                ("therapeutic", Next(node="classical_formula")),
                ("nutrition", Next(category=C.AYURVEDA_AAHARA)),
                ("external_beautification", Next(category=C.COSMETIC)),
                (UNKNOWN, _STOP),
            ),
            context_fields=("intended_use", "dosage_form"),
            references=("category_ayurveda_aahara", "category_cosmetic"),
        ),
        Node(
            id="classical_formula",
            **_keys("classical_formula"),
            choices=_choices("yes", "no"),
            transitions=(
                ("yes", Next(category=C.CLASSICAL)),
                ("no", Next(node="schedule_combination")),
                (UNKNOWN, _STOP),
            ),
            context_fields=("classical_reference", "ingredients", "preparation_method"),
            references=("first_schedule", "category_classical"),
        ),
        Node(
            id="schedule_combination",
            **_keys("schedule_combination"),
            choices=_choices("yes", "no"),
            transitions=(
                ("yes", Next(category=C.PATENT_PROPRIETARY)),
                ("no", Next(node="phytopharmaceutical")),
                (UNKNOWN, _STOP),
            ),
            context_fields=("ingredients", "administration_route"),
            references=("first_schedule", "category_patent_proprietary"),
        ),
        Node(
            id="phytopharmaceutical",
            **_keys("phytopharmaceutical"),
            choices=_choices("yes", "no"),
            transitions=(
                ("yes", Next(category=C.PHYTOPHARMACEUTICAL)),
                ("no", Next(category=C.NEW_OR_NON_CLASSICAL)),
                (UNKNOWN, _STOP),
            ),
            context_fields=("extract_description", "standardization_description", "markers"),
            references=("category_phytopharmaceutical",),
        ),
    ),
    slots=(
        ReferenceSlot("first_schedule", CorpusLane.INDIA, f"{_V}.slot.first_schedule"),
        ReferenceSlot("category_classical", CorpusLane.INDIA, f"{_V}.slot.category_classical"),
        ReferenceSlot("category_patent_proprietary", CorpusLane.INDIA, f"{_V}.slot.category_patent_proprietary"),
        ReferenceSlot("category_new_or_non_classical", CorpusLane.INDIA, f"{_V}.slot.category_new_or_non_classical"),
        ReferenceSlot("category_phytopharmaceutical", CorpusLane.INDIA, f"{_V}.slot.category_phytopharmaceutical"),
        ReferenceSlot("category_ayurveda_aahara", CorpusLane.INDIA, f"{_V}.slot.category_ayurveda_aahara"),
        ReferenceSlot("category_cosmetic", CorpusLane.INDIA, f"{_V}.slot.category_cosmetic"),
    ),
    category_references=(
        (C.CLASSICAL, ("category_classical",)),
        (C.PATENT_PROPRIETARY, ("category_patent_proprietary",)),
        (C.NEW_OR_NON_CLASSICAL, ("category_new_or_non_classical",)),
        (C.PHYTOPHARMACEUTICAL, ("category_phytopharmaceutical",)),
        (C.AYURVEDA_AAHARA, ("category_ayurveda_aahara",)),
        (C.COSMETIC, ("category_cosmetic",)),
    ),
)
