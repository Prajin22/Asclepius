"""history_general, version 2 — the Phase 5B general symptom-history tree.

    status          engineering_draft
    clinical_review required

ENGINEERING DRAFT. CLINICAL REVIEW REQUIRED. This is a reasonable structure for
a first conversation about a new complaint, written by engineers. It has not
been reviewed by a clinician, it is not validated against any guideline, it
does not cover every history, and it must not be described as any of those
things. It is not a diagnostic tree: a branch chooses the next question and
nothing else.

    current_problem ─ onset ─ duration? ─ location ─ location.other?
    ─ character ─ character.other? ─ radiation ─ radiation.location?
    ─ associated ─ associated.other? ─ aggravating ─ aggravating.other?
    ─ relieving ─ relieving.other? ─ history ─ history.details?
    ─ medications ─ medications.details? ─ allergies ─ allergies.details?
    ─ review

`?` marks a follow-up, asked only when the question before it was answered in
a way that opens it.

Two rules shape every question:

* **Every tap question offers an honest way out** — "not sure", and where it
  fits "nothing noticed" or "none of these" — so it can be required without
  forcing anyone to pick an answer they do not believe.
* **Every free-text question can be declined**, because being made to type
  something is not the same as having something to say. The one exception is
  the first question: a conversation about a problem needs the problem.

Localisation keys are derived mechanically (see `_q`, `_help`, `_c`) and live
under `conversation.question`, `conversation.help` and `conversation.choice`,
apart from v1's `conversation.q` / `conversation.option`, because the catalogue
is nested and v1's `conversation.q.symptom.duration` is a leaf that a v2 key
underneath it would collide with. No key here has a translation yet.
"""

from app.conversation.model import Branch, FlowDefinition, Option, QuestionDefinition
from app.models.enums import ConversationSection as S
from app.models.enums import FactCategory
from app.models.enums import ResponseType as T


def _q(question_id: str, version: int = 1) -> str:
    """Prompt key. Versioned, so rewording is a new key and old answers keep
    rendering against the wording the patient actually saw."""
    return f"conversation.question.{question_id}.v{version}"


def _help(question_id: str, version: int = 1) -> str:
    return f"conversation.help.{question_id}.v{version}"


def _c(option_set: str, option_id: str, *, exclusive: bool = False) -> Option:
    return Option(option_id, f"conversation.choice.{option_set}.{option_id}", exclusive)


# Shared answers. `not_sure` is exclusive only where several choices can be
# ticked; on a single choice it is already alone.
YES = _c("common", "yes")
NO = _c("common", "no")
NOT_SURE = _c("common", "not_sure")
NOT_SURE_ALONE = _c("common", "not_sure", exclusive=True)
OTHER = _c("common", "other")
NONE_OF_THESE = _c("common", "none_of_these", exclusive=True)
NOTHING_NOTICED = _c("common", "nothing_noticed", exclusive=True)

YES_NO_NOT_SURE = (YES, NO, NOT_SURE)

ONSET = (
    _c("onset", "today"),
    _c("onset", "days_ago"),
    _c("onset", "weeks_ago"),
    _c("onset", "months_ago"),
    _c("onset", "years_ago"),
    NOT_SURE,
)

LOCATION = (
    _c("location", "head"),
    _c("location", "chest"),
    _c("location", "abdomen"),
    _c("location", "back"),
    _c("location", "arm"),
    _c("location", "leg"),
    OTHER,
    NOT_SURE,
)

# Descriptions the patient chooses. Not mapped to anything: "burning" is stored
# as "burning", never as a category of pain.
CHARACTER = (
    _c("character", "sharp"),
    _c("character", "dull"),
    _c("character", "burning"),
    _c("character", "aching"),
    _c("character", "throbbing"),
    _c("character", "pressure"),
    _c("character", "cramping"),
    OTHER,
    NOT_SURE_ALONE,
)

# Kept deliberately short. "None of these" means none of *these* — it is not a
# statement that the patient has no other symptoms, and nothing records it as one.
ASSOCIATED = (
    _c("associated", "nausea"),
    _c("associated", "vomiting"),
    _c("associated", "dizziness"),
    _c("associated", "fever"),
    _c("associated", "cough"),
    _c("associated", "shortness_of_breath"),
    _c("associated", "fatigue"),
    _c("associated", "weakness"),
    OTHER,
    NONE_OF_THESE,
    NOT_SURE_ALONE,
)

# What the patient has noticed. Recorded as their observation, never as a cause.
AGGRAVATING = (
    _c("aggravating", "movement"),
    _c("aggravating", "activity"),
    _c("aggravating", "food"),
    _c("aggravating", "position"),
    _c("aggravating", "time_of_day"),
    OTHER,
    NOTHING_NOTICED,
    NOT_SURE_ALONE,
)

# What the patient has noticed helps. Recorded as their observation; nothing
# downstream turns "rest helps" into "should rest".
RELIEVING = (
    _c("relieving", "rest"),
    _c("relieving", "position"),
    _c("relieving", "food"),
    _c("relieving", "medication"),
    OTHER,
    NOTHING_NOTICED,
    NOT_SURE_ALONE,
)


def _yes(trigger: str, name: str) -> Branch:
    """Open when the trigger was answered "yes"."""
    return Branch(
        predicate_id=f"{name}_is_yes",
        trigger=trigger,
        when_chosen=frozenset({"yes"}),
        opened=f"{name}_reported",
        closed=f"{name}_not_reported",
    )


def _other(trigger: str, name: str) -> Branch:
    """Open when the trigger's answer includes "other"."""
    return Branch(
        predicate_id=f"{name}_includes_other",
        trigger=trigger,
        when_chosen=frozenset({"other"}),
        opened=f"{name}_other_chosen",
        closed=f"{name}_other_not_chosen",
    )


FLOW = FlowDefinition(
    flow_id="history_general",
    version=2,
    questions=(
        # ---- current problem: the patient's own words, first ----
        QuestionDefinition(
            id="current_problem.primary", version=1, order=10,
            section=S.CURRENT_PROBLEM, response_type=T.FREE_TEXT,
            prompt_key=_q("current_problem.primary"),
            help_key=_help("current_problem.primary"),
            category=FactCategory.SYMPTOM,
        ),
        # ---- onset and duration ----
        QuestionDefinition(
            id="symptom.onset.when", version=1, order=20,
            section=S.ONSET_DURATION, response_type=T.SINGLE_CHOICE,
            prompt_key=_q("symptom.onset.when"),
            options=ONSET,
        ),
        QuestionDefinition(
            # Version 2: v1 asked this of everyone, required, as a number only.
            # Here it is optional, asked only once the patient roughly knows when
            # it started, and it takes words ("some time ago") as readily as a
            # number — words are kept as words, never converted.
            id="symptom.duration", version=2, order=30,
            section=S.ONSET_DURATION, response_type=T.DURATION,
            prompt_key=_q("symptom.duration", 2),
            help_key=_help("symptom.duration", 2),
            required=False,
            branch=Branch(
                predicate_id="onset_is_known",
                trigger="symptom.onset.when",
                when_chosen=frozenset({"today", "days_ago", "weeks_ago", "months_ago", "years_ago"}),
                opened="onset_known",
                closed="onset_not_known",
            ),
        ),
        # ---- location ----
        QuestionDefinition(
            id="symptom.location", version=1, order=40,
            section=S.LOCATION, response_type=T.SINGLE_CHOICE,
            prompt_key=_q("symptom.location"),
            options=LOCATION,
        ),
        QuestionDefinition(
            id="symptom.location.other", version=1, order=45,
            section=S.LOCATION, response_type=T.FREE_TEXT,
            prompt_key=_q("symptom.location.other"),
            required=False, branch=_other("symptom.location", "location"),
        ),
        # ---- character ----
        QuestionDefinition(
            # Version 2: v1 was a single choice, asked only about pain.
            id="symptom.character", version=2, order=50,
            section=S.CHARACTER, response_type=T.MULTI_CHOICE,
            prompt_key=_q("symptom.character", 2),
            options=CHARACTER,
        ),
        QuestionDefinition(
            id="symptom.character.other", version=1, order=55,
            section=S.CHARACTER, response_type=T.FREE_TEXT,
            prompt_key=_q("symptom.character.other"),
            required=False, branch=_other("symptom.character", "character"),
        ),
        # ---- radiation or spread ----
        QuestionDefinition(
            id="symptom.radiation", version=1, order=60,
            section=S.RADIATION_OR_SPREAD, response_type=T.YES_NO,
            prompt_key=_q("symptom.radiation"),
            options=YES_NO_NOT_SURE,
        ),
        QuestionDefinition(
            id="symptom.radiation.location", version=1, order=65,
            section=S.RADIATION_OR_SPREAD, response_type=T.FREE_TEXT,
            prompt_key=_q("symptom.radiation.location"),
            required=False, branch=_yes("symptom.radiation", "radiation"),
        ),
        # ---- associated symptoms ----
        QuestionDefinition(
            # Version 2: v1 was free text.
            id="symptom.associated", version=2, order=70,
            section=S.ASSOCIATED_SYMPTOMS, response_type=T.MULTI_CHOICE,
            prompt_key=_q("symptom.associated", 2),
            options=ASSOCIATED,
        ),
        QuestionDefinition(
            id="symptom.associated.other", version=1, order=75,
            section=S.ASSOCIATED_SYMPTOMS, response_type=T.FREE_TEXT,
            prompt_key=_q("symptom.associated.other"),
            required=False, category=FactCategory.SYMPTOM,
            branch=_other("symptom.associated", "associated"),
        ),
        # ---- what makes it worse ----
        QuestionDefinition(
            # Version 2: v1 was free text.
            id="symptom.aggravating", version=2, order=80,
            section=S.AGGRAVATING_FACTORS, response_type=T.MULTI_CHOICE,
            prompt_key=_q("symptom.aggravating", 2),
            options=AGGRAVATING,
        ),
        QuestionDefinition(
            id="symptom.aggravating.other", version=1, order=85,
            section=S.AGGRAVATING_FACTORS, response_type=T.FREE_TEXT,
            prompt_key=_q("symptom.aggravating.other"),
            required=False, branch=_other("symptom.aggravating", "aggravating"),
        ),
        # ---- what makes it better ----
        QuestionDefinition(
            # Version 2: v1 was free text.
            id="symptom.relieving", version=2, order=90,
            section=S.RELIEVING_FACTORS, response_type=T.MULTI_CHOICE,
            prompt_key=_q("symptom.relieving", 2),
            options=RELIEVING,
        ),
        QuestionDefinition(
            id="symptom.relieving.other", version=1, order=95,
            section=S.RELIEVING_FACTORS, response_type=T.FREE_TEXT,
            prompt_key=_q("symptom.relieving.other"),
            required=False, branch=_other("symptom.relieving", "relieving"),
        ),
        # ---- relevant history: no list of diseases is ever offered ----
        QuestionDefinition(
            id="history.relevant", version=1, order=100,
            section=S.RELEVANT_HISTORY, response_type=T.YES_NO,
            prompt_key=_q("history.relevant"),
            options=YES_NO_NOT_SURE,
        ),
        QuestionDefinition(
            id="history.relevant.details", version=1, order=105,
            section=S.RELEVANT_HISTORY, response_type=T.FREE_TEXT,
            prompt_key=_q("history.relevant.details"),
            required=False, category=FactCategory.MEDICAL_HISTORY,
            branch=_yes("history.relevant", "history"),
        ),
        # ---- medications: recorded as described, never checked or advised on ----
        QuestionDefinition(
            id="medications.current", version=1, order=110,
            section=S.MEDICATIONS, response_type=T.YES_NO,
            prompt_key=_q("medications.current"),
            options=YES_NO_NOT_SURE,
        ),
        QuestionDefinition(
            id="medications.details", version=1, order=115,
            section=S.MEDICATIONS, response_type=T.FREE_TEXT,
            prompt_key=_q("medications.details"),
            required=False, category=FactCategory.MEDICATION,
            branch=_yes("medications.current", "medications"),
        ),
        # ---- allergies: "not sure" is never recorded as "no known allergies" ----
        QuestionDefinition(
            id="allergies.known", version=1, order=120,
            section=S.ALLERGIES, response_type=T.YES_NO,
            prompt_key=_q("allergies.known"),
            options=YES_NO_NOT_SURE,
        ),
        QuestionDefinition(
            id="allergies.details", version=1, order=125,
            section=S.ALLERGIES, response_type=T.FREE_TEXT,
            prompt_key=_q("allergies.details"),
            required=False, category=FactCategory.ALLERGY,
            branch=_yes("allergies.known", "allergies"),
        ),
    ),
)
