"""history_general, version 1 — the Phase 5A flow. Frozen.

Kept so that any session started under it is still walked under it: a flow
version is a promise that answers already given are never reinterpreted by a
later tree. New sessions start on the current version, not this one.

Re-expressed in Phase 5B as declarative branches, with the same questions, the
same keys and the same branching as Phase 5A. Its fingerprint is pinned in
`app.conversation.flow.PUBLISHED`; changing anything here fails that test.

ENGINEERING DRAFT. Not clinically reviewed.
"""

from app.conversation.model import Branch, FlowDefinition, Option, QuestionDefinition
from app.models.enums import ConversationSection as S
from app.models.enums import FactCategory, FactSubject
from app.models.enums import ResponseType as T

YES_NO_UNSURE = (
    Option("yes", "conversation.option.yes"),
    Option("no", "conversation.option.no"),
    Option("unsure", "conversation.option.unsure"),
)

BODY_SITES = (
    Option("head", "conversation.option.site.head"),
    Option("chest", "conversation.option.site.chest"),
    Option("abdomen", "conversation.option.site.abdomen"),
    Option("back", "conversation.option.site.back"),
    Option("limbs", "conversation.option.site.limbs"),
    Option("other", "conversation.option.site.other"),
)

PAIN_CHARACTER = (
    Option("sharp", "conversation.option.character.sharp"),
    Option("dull", "conversation.option.character.dull"),
    Option("burning", "conversation.option.character.burning"),
    Option("throbbing", "conversation.option.character.throbbing"),
    Option("cramping", "conversation.option.character.cramping"),
    Option("other", "conversation.option.character.other"),
)

_PAIN = Branch(
    predicate_id="is_pain_is_yes",
    trigger="symptom.is_pain",
    when_chosen=frozenset({"yes"}),
    opened="pain_reported",
    closed="pain_not_reported",
)

FLOW = FlowDefinition(
    flow_id="history_general",
    version=1,
    questions=(
        QuestionDefinition(
            id="problem.description", version=1, order=10,
            section=S.CURRENT_PROBLEM, response_type=T.FREE_TEXT,
            prompt_key="conversation.q.problem.description",
            help_key="conversation.q.problem.descriptionHelp",
            category=FactCategory.SYMPTOM,
        ),
        QuestionDefinition(
            id="symptom.duration", version=1, order=20,
            section=S.ONSET_DURATION, response_type=T.DURATION,
            prompt_key="conversation.q.symptom.duration",
            category=FactCategory.DURATION,
        ),
        QuestionDefinition(
            id="symptom.happened_before", version=1, order=30,
            section=S.ONSET_DURATION, response_type=T.YES_NO,
            prompt_key="conversation.q.symptom.happenedBefore",
            options=YES_NO_UNSURE, required=False,
        ),
        QuestionDefinition(
            id="symptom.is_pain", version=1, order=40,
            section=S.LOCATION, response_type=T.YES_NO,
            prompt_key="conversation.q.symptom.isPain",
            options=YES_NO_UNSURE,
        ),
        QuestionDefinition(
            id="symptom.site", version=1, order=50,
            section=S.LOCATION, response_type=T.SINGLE_CHOICE,
            prompt_key="conversation.q.symptom.site",
            options=BODY_SITES, branch=_PAIN,
        ),
        QuestionDefinition(
            id="symptom.character", version=1, order=60,
            section=S.CHARACTER, response_type=T.SINGLE_CHOICE,
            prompt_key="conversation.q.symptom.character",
            options=PAIN_CHARACTER, required=False, branch=_PAIN,
        ),
        QuestionDefinition(
            id="symptom.radiates", version=1, order=70,
            section=S.CHARACTER, response_type=T.YES_NO,
            prompt_key="conversation.q.symptom.radiates",
            options=YES_NO_UNSURE, required=False, branch=_PAIN,
        ),
        QuestionDefinition(
            id="symptom.associated", version=1, order=80,
            section=S.ASSOCIATED_SYMPTOMS, response_type=T.FREE_TEXT,
            prompt_key="conversation.q.symptom.associated",
            required=False, category=FactCategory.SYMPTOM,
        ),
        QuestionDefinition(
            id="symptom.aggravating", version=1, order=90,
            section=S.AGGRAVATING_RELIEVING, response_type=T.FREE_TEXT,
            prompt_key="conversation.q.symptom.aggravating",
            required=False,
        ),
        QuestionDefinition(
            id="symptom.relieving", version=1, order=100,
            section=S.AGGRAVATING_RELIEVING, response_type=T.FREE_TEXT,
            prompt_key="conversation.q.symptom.relieving",
            required=False,
        ),
        QuestionDefinition(
            id="history.conditions", version=1, order=110,
            section=S.RELEVANT_HISTORY, response_type=T.FREE_TEXT,
            prompt_key="conversation.q.history.conditions",
            required=False, category=FactCategory.MEDICAL_HISTORY,
        ),
        QuestionDefinition(
            id="history.family_conditions", version=1, order=120,
            section=S.RELEVANT_HISTORY, response_type=T.FREE_TEXT,
            prompt_key="conversation.q.history.familyConditions",
            required=False, category=FactCategory.MEDICAL_HISTORY,
            # Asked about relatives, so anything it produces is a relative's.
            subject=FactSubject.FAMILY,
        ),
        QuestionDefinition(
            id="medication.taking_any", version=1, order=130,
            section=S.MEDICATIONS, response_type=T.YES_NO,
            prompt_key="conversation.q.medication.takingAny",
            options=YES_NO_UNSURE,
        ),
        QuestionDefinition(
            id="medication.which", version=1, order=140,
            section=S.MEDICATIONS, response_type=T.FREE_TEXT,
            prompt_key="conversation.q.medication.which",
            category=FactCategory.MEDICATION,
            branch=Branch(
                predicate_id="taking_any_is_yes",
                trigger="medication.taking_any",
                when_chosen=frozenset({"yes"}),
                opened="medication_reported",
                closed="medication_not_reported",
            ),
        ),
        QuestionDefinition(
            id="allergy.any", version=1, order=150,
            section=S.ALLERGIES, response_type=T.YES_NO,
            prompt_key="conversation.q.allergy.any",
            options=YES_NO_UNSURE,
        ),
        QuestionDefinition(
            id="allergy.which", version=1, order=160,
            section=S.ALLERGIES, response_type=T.FREE_TEXT,
            prompt_key="conversation.q.allergy.which",
            category=FactCategory.ALLERGY,
            branch=Branch(
                predicate_id="allergy_any_is_yes",
                trigger="allergy.any",
                when_chosen=frozenset({"yes"}),
                opened="allergy_reported",
                closed="allergy_not_reported",
            ),
        ),
    ),
)
