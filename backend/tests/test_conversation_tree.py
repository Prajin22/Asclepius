"""history_general v2, the Phase 5B tree, tested as pure data and pure functions.

No database here. The engine is deterministic and has no I/O, so the tree's
structure, every branch, every reason code and every answer shape can be
checked directly and exhaustively. The service tests then check that the same
engine is what actually runs.

Nothing here asserts that a question is clinically right. The tree is an
engineering draft awaiting clinical review; these tests check that it is walked
honestly.
"""

import itertools
import random
import re

import pytest

from app.conversation import engine
from app.conversation import flow as flows
from app.conversation.model import (
    ENGINE_REASON_CODES,
    FLOW_COMPLETE,
    FLOW_SEQUENCE,
    SLUG,
    TRIGGER_DECLINED,
    TRIGGER_NOT_APPLICABLE,
    Answer,
    Branch,
    ClinicalReview,
    FlowDefinition,
    FlowDefinitionError,
    FlowStatus,
    Option,
    QuestionDefinition,
    Status,
)
from app.models.enums import ConversationSection, FactCategory, FactSubject, ResponseType
from app.services.errors import InvalidInput

V1 = flows.get_flow("history_general", 1)
V2 = flows.get_flow("history_general", 2)
ALL_FLOWS = tuple(flows.FLOWS.values())


def picked(*choices: str) -> Answer:
    return Answer(choices=frozenset(choices))


DECLINED = Answer(declined=True)
WORDS = Answer()  # a free-text answer: the engine sees no words, only that it was answered


def walk(answers: dict[str, Answer]) -> list[str]:
    """The order v2 asks its questions in, given the answers it will receive."""
    asked, given = [], {}
    while (selection := engine.next_question(V2, given)).question is not None:
        qid = selection.question.id
        asked.append(qid)
        given[qid] = answers.get(qid, WORDS if selection.question.response_type in (
            ResponseType.FREE_TEXT, ResponseType.DURATION) else picked("not_sure"))
    return asked


# --------------------------------------------------------------------------
# what the flow is, and what it must never be described as
# --------------------------------------------------------------------------


def test_the_new_conversation_starts_on_v2():
    assert flows.FLOW_VERSION == 2
    assert flows.current_flow() is V2


def test_every_flow_is_an_engineering_draft_awaiting_clinical_review():
    for f in ALL_FLOWS:
        assert f.status == FlowStatus.ENGINEERING_DRAFT
        assert f.clinical_review == ClinicalReview.REQUIRED


def test_no_published_flow_has_been_edited_in_place():
    for key, f in flows.FLOWS.items():
        assert f.fingerprint() == flows.PUBLISHED[key], (
            f"{key} was changed after it was published. Answers already given under it "
            "would be reinterpreted. Undo the edit and publish a new version instead."
        )


def test_every_published_flow_is_pinned():
    assert set(flows.FLOWS) == set(flows.PUBLISHED)


def test_the_v2_tree_has_the_sections_the_history_walks_in_order():
    sections = list(dict.fromkeys(q.section for q in V2.questions))
    assert sections == [
        ConversationSection.CURRENT_PROBLEM,
        ConversationSection.ONSET_DURATION,
        ConversationSection.LOCATION,
        ConversationSection.CHARACTER,
        ConversationSection.RADIATION_OR_SPREAD,
        ConversationSection.ASSOCIATED_SYMPTOMS,
        ConversationSection.AGGRAVATING_FACTORS,
        ConversationSection.RELIEVING_FACTORS,
        ConversationSection.RELEVANT_HISTORY,
        ConversationSection.MEDICATIONS,
        ConversationSection.ALLERGIES,
    ]
    # Review is a step, not a question, so no question carries it.
    assert all(q.section != ConversationSection.REVIEW for q in V2.questions)


def test_order_is_explicit_numbers_not_list_position():
    orders = [q.order for q in V2.questions]
    assert orders == sorted(orders)
    assert len(set(orders)) == len(orders)
    # Every follow-up is the question immediately after the one that opens it.
    ids = [q.id for q in V2.questions]
    for q in V2.questions:
        if q.branch:
            assert ids.index(q.id) == ids.index(q.branch.trigger) + 1, q.id


# --------------------------------------------------------------------------
# structure the engine depends on
# --------------------------------------------------------------------------


@pytest.mark.parametrize("f", ALL_FLOWS, ids=lambda f: f"v{f.version}")
def test_every_flow_is_structurally_valid(f):
    f.validate()  # raises with every problem found


def test_a_branch_whose_trigger_comes_later_is_refused():
    late = FlowDefinition("t", 1, (
        QuestionDefinition("b", 1, 10, ConversationSection.LOCATION, ResponseType.FREE_TEXT, "k.b",
                           branch=Branch("p", "a", frozenset({"yes"}), "o", "c")),
        QuestionDefinition("a", 1, 20, ConversationSection.LOCATION, ResponseType.YES_NO, "k.a",
                           options=(Option("yes", "k.yes"), Option("no", "k.no"))),
    ))
    with pytest.raises(FlowDefinitionError, match="does not come before"):
        late.validate()


def test_a_branch_on_an_option_the_trigger_does_not_offer_is_refused():
    bad = FlowDefinition("t", 1, (
        QuestionDefinition("a", 1, 10, ConversationSection.LOCATION, ResponseType.YES_NO, "k.a",
                           options=(Option("yes", "k.yes"), Option("no", "k.no"))),
        QuestionDefinition("b", 1, 20, ConversationSection.LOCATION, ResponseType.FREE_TEXT, "k.b",
                           branch=Branch("p", "a", frozenset({"maybe"}), "o", "c")),
    ))
    with pytest.raises(FlowDefinitionError, match="does not offer"):
        bad.validate()


def test_question_ids_within_a_flow_map_to_one_version():
    for f in ALL_FLOWS:
        assert len(f.by_id) == len(f.questions)


def test_a_question_id_and_version_means_the_same_question_in_every_flow():
    seen: dict[tuple[str, int], QuestionDefinition] = {}
    for f in ALL_FLOWS:
        for q in f.questions:
            earlier = seen.setdefault((q.id, q.version), q)
            assert (earlier.prompt_key, earlier.response_type, earlier.options) == (
                q.prompt_key, q.response_type, q.options
            ), f"{q.id} v{q.version} means different things in different flows"


def test_a_question_whose_meaning_changed_got_a_new_version():
    for qid in ("symptom.duration", "symptom.character", "symptom.associated",
                "symptom.aggravating", "symptom.relieving"):
        assert V1.question(qid).version == 1
        assert V2.question(qid).version == 2


# --------------------------------------------------------------------------
# option ids, keys, reason codes — nothing stored depends on wording
# --------------------------------------------------------------------------


def _all_keys() -> set[str]:
    keys = set()
    for f in ALL_FLOWS:
        for q in f.questions:
            keys.add(q.prompt_key)
            if q.help_key:
                keys.add(q.help_key)
            keys.update(o.label_key for o in q.options)
        keys.update(f"conversation.reason.{code}" for code in f.reason_codes())
    return keys


def test_no_localisation_key_is_both_a_string_and_a_group():
    """The catalogue is nested and looked up by splitting on '.', so a key that
    is a leaf cannot also have keys beneath it. v2's ids nest ("symptom.radiation"
    and "symptom.radiation.location"); this is what would break first."""
    keys = sorted(_all_keys())
    for a, b in itertools.combinations(keys, 2):
        assert not b.startswith(a + "."), f"{a} is a string and also the parent of {b}"
        assert not a.startswith(b + "."), f"{b} is a string and also the parent of {a}"


def test_v2_keys_follow_the_versioned_convention():
    for q in V2.questions:
        assert q.prompt_key == f"conversation.question.{q.id}.v{q.version}"
        if q.help_key:
            assert q.help_key == f"conversation.help.{q.id}.v{q.version}"
        for o in q.options:
            assert re.fullmatch(rf"conversation\.choice\.[a-z_]+\.{o.id}", o.label_key)


def test_question_ids_are_stable_identifiers_not_wording():
    for q in V2.questions:
        assert re.fullmatch(r"[a-z_]+(\.[a-z_]+)+", q.id), q.id
        assert q.id not in q.prompt_key.split(".")[-1]


def test_option_ids_are_slugs_and_never_their_labels():
    for f in ALL_FLOWS:
        for q in f.questions:
            for o in q.options:
                assert SLUG.match(o.id)
                assert o.id != o.label_key


def test_every_reason_code_is_a_slug():
    for f in ALL_FLOWS:
        for code in f.reason_codes():
            assert SLUG.match(code), code


def test_skip_reasons_never_claim_more_than_the_answer_said():
    """A shut branch is shut for "no" and for "not sure" alike, so its reason
    must be true of both. "not_present" would claim an absence the patient never
    stated; "not_reported" and "not_chosen" claim only what happened."""
    for q in V2.questions:
        if q.branch:
            assert q.branch.closed.endswith(("_not_reported", "_not_chosen", "_not_known")), q.branch.closed
            assert "absent" not in q.branch.closed and "present" not in q.branch.closed


# --------------------------------------------------------------------------
# the honest way out, and "no answer" versus "not asked"
# --------------------------------------------------------------------------


def test_every_required_tap_question_offers_an_honest_way_out():
    for q in V2.questions:
        if q.required and q.options:
            assert "not_sure" in q.option_ids, f"{q.id} forces a choice with no honest exit"


def test_every_free_text_question_except_the_first_can_be_declined():
    free_text = [q for q in V2.questions if q.response_type == ResponseType.FREE_TEXT]
    assert free_text[0].id == "current_problem.primary" and free_text[0].required
    assert all(not q.required for q in free_text[1:])


def test_none_of_these_not_sure_and_nothing_noticed_stand_alone():
    for q in V2.questions:
        if q.response_type == ResponseType.MULTI_CHOICE:
            for o in q.options:
                if o.id in ("none_of_these", "not_sure", "nothing_noticed"):
                    assert o.exclusive, f"{q.id}: {o.id} must not combine with other choices"


def test_no_v2_option_names_a_disease():
    """History is asked about, never offered from a list: a menu of diseases
    invites self-diagnosis."""
    diseases = {"diabetes", "hypertension", "asthma", "cancer", "tuberculosis", "migraine", "heart_disease"}
    offered = {o.id for q in V2.questions for o in q.options}
    assert not offered & diseases


# --------------------------------------------------------------------------
# A. the linear path
# --------------------------------------------------------------------------


def test_a_the_first_question_is_the_patients_own_words():
    selection = engine.next_question(V2, {})
    assert selection.question.id == "current_problem.primary"
    assert selection.question.response_type == ResponseType.FREE_TEXT
    assert selection.reason_code == FLOW_SEQUENCE
    assert selection.trigger_question_id is None


def test_a_everyone_is_asked_the_core_questions_in_order():
    asked = walk({})
    core = [q.id for q in V2.questions if q.branch is None]
    assert [q for q in asked if q in core] == core


def test_a_when_every_branch_stays_shut_only_the_core_is_asked():
    asked = walk({})  # "not sure" everywhere
    assert asked == [q.id for q in V2.questions if q.branch is None]


# --------------------------------------------------------------------------
# B–L. every branch, opened and shut
# --------------------------------------------------------------------------

BRANCHES = [
    # trigger, answer that opens it, follow-up, opened code, closed code
    ("symptom.onset.when", "days_ago", "symptom.duration", "onset_known", "onset_not_known"),
    ("symptom.location", "other", "symptom.location.other", "location_other_chosen", "location_other_not_chosen"),
    ("symptom.character", "other", "symptom.character.other", "character_other_chosen", "character_other_not_chosen"),
    ("symptom.radiation", "yes", "symptom.radiation.location", "radiation_reported", "radiation_not_reported"),
    ("symptom.associated", "other", "symptom.associated.other", "associated_other_chosen", "associated_other_not_chosen"),
    ("symptom.aggravating", "other", "symptom.aggravating.other", "aggravating_other_chosen", "aggravating_other_not_chosen"),
    ("symptom.relieving", "other", "symptom.relieving.other", "relieving_other_chosen", "relieving_other_not_chosen"),
    ("history.relevant", "yes", "history.relevant.details", "history_reported", "history_not_reported"),
    ("medications.current", "yes", "medications.details", "medications_reported", "medications_not_reported"),
    ("allergies.known", "yes", "allergies.details", "allergies_reported", "allergies_not_reported"),
]


def test_every_branch_in_v2_is_covered_here():
    assert {b[2] for b in BRANCHES} == {q.id for q in V2.questions if q.branch}


@pytest.mark.parametrize("trigger,opens,follow_up,opened,closed", BRANCHES, ids=[b[2] for b in BRANCHES])
def test_a_branch_opens_on_its_answer_and_says_why(trigger, opens, follow_up, opened, closed):
    asked = walk({trigger: picked(opens)})
    assert asked[asked.index(trigger) + 1] == follow_up

    before = {q: (picked(opens) if q == trigger else WORDS) for q in asked[: asked.index(follow_up)]}
    selection = engine.next_question(V2, before)
    assert selection.question.id == follow_up
    assert selection.reason_code == opened
    assert selection.trigger_question_id == trigger
    assert selection.predicate_id == V2.question(follow_up).branch.predicate_id


@pytest.mark.parametrize("trigger,opens,follow_up,opened,closed", BRANCHES, ids=[b[2] for b in BRANCHES])
def test_a_branch_stays_shut_otherwise_and_the_skip_says_why(trigger, opens, follow_up, opened, closed):
    opening = V2.question(follow_up).branch.when_chosen
    assert opens in opening
    other_answers = [o for o in V2.question(trigger).option_ids if o not in opening]
    assert other_answers, f"{trigger} has no answer that keeps {follow_up} shut"
    for answer in other_answers:
        asked = walk({trigger: picked(answer)})
        assert follow_up not in asked, f"{trigger}={answer} should not open {follow_up}"

        state = engine.resolve(V2, {trigger: picked(answer)} | {
            q.id: WORDS for q in V2.questions if q.order < V2.question(trigger).order
        }).by_id[follow_up]
        assert state.status == Status.NOT_APPLICABLE
        assert state.reason_code == closed
        assert state.trigger_question_id == trigger


def test_b_radiation_yes_asks_where_it_spreads():
    assert "symptom.radiation.location" in walk({"symptom.radiation": picked("yes")})


def test_c_radiation_no_and_not_sure_both_skip_it_without_claiming_no():
    for answer in ("no", "not_sure"):
        state = engine.resolve(V2, {"symptom.radiation": picked(answer)} | {
            q.id: WORDS for q in V2.questions if q.order < 60
        }).by_id["symptom.radiation.location"]
        assert state.status == Status.NOT_APPLICABLE
        assert state.reason_code == "radiation_not_reported"


def test_d_location_other_asks_where():
    asked = walk({"symptom.location": picked("other")})
    assert asked[asked.index("symptom.location") + 1] == "symptom.location.other"


def test_e_none_of_these_opens_nothing_and_records_no_symptom():
    asked = walk({"symptom.associated": picked("none_of_these")})
    assert "symptom.associated.other" not in asked
    # A tap produces no candidate at all — not "no nausea", not "no symptoms".
    q = V2.question("symptom.associated")
    assert engine.candidate_value(q, None, declined=False) is None


def test_f_associated_other_asks_what_else():
    asked = walk({"symptom.associated": picked("fever", "other")})
    assert asked[asked.index("symptom.associated") + 1] == "symptom.associated.other"


@pytest.mark.parametrize("question,details", [
    ("medications.current", "medications.details"),
    ("allergies.known", "allergies.details"),
])
def test_g_to_j_yes_asks_for_details_no_and_not_sure_do_not(question, details):
    assert details in walk({question: picked("yes")})
    assert details not in walk({question: picked("no")})
    assert details not in walk({question: picked("not_sure")})


def test_k_several_branches_open_at_once_in_order():
    answers = {
        "symptom.location": picked("other"),
        "symptom.radiation": picked("yes"),
        "symptom.associated": picked("nausea", "other"),
        "medications.current": picked("yes"),
        "allergies.known": picked("yes"),
    }
    asked = walk(answers)
    for trigger, follow_up in [
        ("symptom.location", "symptom.location.other"),
        ("symptom.radiation", "symptom.radiation.location"),
        ("symptom.associated", "symptom.associated.other"),
        ("medications.current", "medications.details"),
        ("allergies.known", "allergies.details"),
    ]:
        assert asked.index(follow_up) == asked.index(trigger) + 1
    assert asked == sorted(asked, key=lambda q: V2.question(q).order)


def test_l_every_shut_branch_is_recorded_as_not_applicable_never_as_an_answer():
    answers = {q.id: WORDS for q in V2.questions if q.branch is None}
    answers.update({q: picked("no") for q in ("symptom.radiation", "history.relevant",
                                                "medications.current", "allergies.known")})
    answers.update({q: picked("not_sure") for q in ("symptom.onset.when", "symptom.location",
                                                      "symptom.character", "symptom.associated",
                                                      "symptom.aggravating", "symptom.relieving")})
    r = engine.resolve(V2, answers)
    skipped = {s.question.id for s in r.not_applicable}
    assert skipped == {q.id for q in V2.questions if q.branch}
    assert r.next is None
    assert engine.select(r).reason_code == FLOW_COMPLETE
    # Nothing in the answers mentions a skipped question.
    assert not skipped & set(answers)


# --------------------------------------------------------------------------
# M–N. what a valid answer is
# --------------------------------------------------------------------------


def q2(qid: str) -> QuestionDefinition:
    return V2.question(qid)


@pytest.mark.parametrize("qid,value,code", [
    ("symptom.location", {"choices": ["kidney"]}, "invalid_choice"),
    ("symptom.location", {"choices": ["head", "chest"]}, "invalid_choice"),
    ("symptom.radiation", {"choices": ["maybe"]}, "invalid_choice"),
    ("symptom.associated", {"choices": []}, "invalid_choice"),
    ("symptom.associated", {"choices": ["fever", "none_of_these"]}, "exclusive_choice_combined"),
    ("symptom.associated", {"choices": ["not_sure", "cough"]}, "exclusive_choice_combined"),
    ("symptom.relieving", {"choices": ["rest", "nothing_noticed"]}, "exclusive_choice_combined"),
])
def test_m_an_option_that_was_not_offered_or_does_not_fit_is_refused(qid, value, code):
    with pytest.raises(InvalidInput) as refused:
        engine.validate(q2(qid), None, value, declined=False)
    assert refused.value.code == code


@pytest.mark.parametrize("qid,text,value,code", [
    ("current_problem.primary", "headache", {"choices": ["yes"]}, "value_not_applicable"),
    ("current_problem.primary", "headache", {"duration": {"amount": 2, "unit": "days"}}, "value_not_applicable"),
    ("symptom.radiation", "it goes to my arm", {"choices": ["yes"]}, "text_not_applicable"),
    ("symptom.radiation", None, {"duration": {"amount": 2, "unit": "days"}}, "value_not_applicable"),
    ("symptom.duration", None, {"choices": ["days_ago"]}, "value_not_applicable"),
    ("symptom.duration", None, {"duration": {"amount": -3, "unit": "days"}}, "invalid_duration"),
    ("symptom.duration", None, {"duration": {"amount": 3, "unit": "fortnights"}}, "invalid_duration"),
    ("symptom.duration", None, {"duration": {"amount": True, "unit": "days"}}, "invalid_duration"),
    ("symptom.duration", None, {"diagnosis": "flu"}, "value_not_applicable"),
])
def test_n_a_value_of_the_wrong_shape_for_the_question_is_refused(qid, text, value, code):
    with pytest.raises(InvalidInput) as refused:
        engine.validate(q2(qid), text, value, declined=False)
    assert refused.value.code == code


def test_a_required_question_cannot_be_declined_and_an_optional_one_can():
    with pytest.raises(InvalidInput) as refused:
        engine.validate(q2("symptom.radiation"), None, None, declined=True)
    assert refused.value.code == "answer_required"
    assert engine.validate(q2("symptom.radiation.location"), None, None, declined=True) == (None, {})


def test_a_declined_question_cannot_also_carry_an_answer():
    with pytest.raises(InvalidInput) as refused:
        engine.validate(q2("allergies.details"), "penicillin", None, declined=True)
    assert refused.value.code == "declined_with_answer"


def test_an_overlong_answer_is_refused_not_shortened():
    with pytest.raises(InvalidInput) as refused:
        engine.validate(q2("current_problem.primary"), "x" * (engine.MAX_ANSWER_CHARS + 1), None, False)
    assert refused.value.code == "answer_too_long"


# --------------------------------------------------------------------------
# negative answers are not collapsed
# --------------------------------------------------------------------------


def test_not_sure_is_never_stored_as_no():
    _, yes = engine.validate(q2("allergies.known"), None, {"choices": ["yes"]}, False)
    _, no = engine.validate(q2("allergies.known"), None, {"choices": ["no"]}, False)
    _, unsure = engine.validate(q2("allergies.known"), None, {"choices": ["not_sure"]}, False)
    assert yes == {"choices": ["yes"], "bool": True}
    assert no == {"choices": ["no"], "bool": False}
    # Neither true nor false: there is no `bool` to misread as "no known allergies".
    assert unsure == {"choices": ["not_sure"]}


def test_no_answer_not_asked_no_and_not_sure_are_four_different_states():
    base = {q.id: WORDS for q in V2.questions if q.order < 120}
    no = engine.resolve(V2, base | {"allergies.known": picked("no")})
    unsure = engine.resolve(V2, base | {"allergies.known": picked("not_sure")})
    yes_declined = engine.resolve(V2, base | {"allergies.known": picked("yes"), "allergies.details": DECLINED})

    # "No" and "not sure" are both answered — the difference lives in the answer.
    assert no.by_id["allergies.known"].status == unsure.by_id["allergies.known"].status == Status.ANSWERED
    # Either way the follow-up was not asked.
    assert no.by_id["allergies.details"].status == Status.NOT_APPLICABLE
    # "Yes" then declining the details is "no answer", not "not asked".
    assert yes_declined.by_id["allergies.details"].status == Status.DECLINED


def test_words_are_kept_as_words_and_never_turned_into_a_duration():
    text, value = engine.validate(q2("symptom.duration"), "some time ago", None, False)
    assert (text, value) == ("some time ago", {})
    text, value = engine.validate(q2("symptom.duration"), "three days", None, False)
    assert (text, value) == ("three days", {})  # not {"duration": {"amount": 3, ...}}
    text, value = engine.validate(q2("symptom.duration"), None, {"duration": {"amount": 3, "unit": "days"}}, False)
    assert (text, value) == (None, {"duration": {"amount": 3, "unit": "days"}})


def test_a_description_is_stored_as_chosen_never_mapped_to_a_category():
    _, value = engine.validate(q2("symptom.character"), None, {"choices": ["burning"]}, False)
    assert value == {"choices": ["burning"]}


def test_the_same_taps_in_a_different_order_are_the_same_stored_answer():
    _, a = engine.validate(q2("symptom.associated"), None, {"choices": ["fever", "nausea", "cough"]}, False)
    _, b = engine.validate(q2("symptom.associated"), None, {"choices": ["cough", "fever", "nausea"]}, False)
    assert a == b == {"choices": ["nausea", "fever", "cough"]}  # the question's own order


# --------------------------------------------------------------------------
# candidates
# --------------------------------------------------------------------------


def test_only_free_text_with_a_category_produces_a_candidate():
    produces = {q.id for q in V2.questions
                if engine.candidate_value(q, "some words", declined=False) is not None}
    assert produces == {
        "current_problem.primary",
        "symptom.associated.other",
        "history.relevant.details",
        "medications.details",
        "allergies.details",
    }


def test_a_candidate_is_the_patients_own_words():
    assert engine.candidate_value(q2("allergies.details"), "  penicillin, I think  ", False) == "penicillin, I think"


def test_a_declined_answer_produces_no_candidate():
    assert engine.candidate_value(q2("allergies.details"), None, declined=True) is None


def test_v2_asks_only_about_the_patient_themself():
    """No v2 question asks about a relative, so every candidate is the
    patient's own. Attribution still comes from the question (D-062): if a
    family question is added, it says so there."""
    assert {q.subject for q in V2.questions} == {FactSubject.SELF}


def test_categories_map_only_to_what_phase_2_already_uses():
    used = {q.category for q in V2.questions if q.category}
    assert used <= {FactCategory.SYMPTOM, FactCategory.MEDICAL_HISTORY, FactCategory.MEDICATION, FactCategory.ALLERGY}


# --------------------------------------------------------------------------
# V–W. versions
# --------------------------------------------------------------------------


def test_v_an_old_flow_is_still_walked_under_its_own_tree():
    assert engine.next_question(V1, {}).question.id == "problem.description"
    assert engine.next_question(V2, {}).question.id == "current_problem.primary"
    # v1's pain branch is still v1's pain branch.
    after = {"problem.description": WORDS, "symptom.duration": WORDS,
             "symptom.happened_before": picked("no"), "symptom.is_pain": picked("yes")}
    selection = engine.next_question(V1, after)
    assert (selection.question.id, selection.reason_code) == ("symptom.site", "pain_reported")


def test_v_a_session_can_never_be_walked_under_a_flow_that_does_not_exist():
    with pytest.raises(flows.UnknownFlow):
        flows.get_flow("history_general", 99)


def test_w_the_same_question_id_resolves_to_the_wording_of_its_own_flow():
    assert V1.question("symptom.duration").prompt_key == "conversation.q.symptom.duration"
    assert V2.question("symptom.duration").prompt_key == "conversation.question.symptom.duration.v2"


# --------------------------------------------------------------------------
# X. determinism
# --------------------------------------------------------------------------


def test_x_the_same_answers_give_the_same_next_question_every_time():
    answers = {"current_problem.primary": WORDS, "symptom.onset.when": picked("weeks_ago"),
               "symptom.duration": WORDS, "symptom.location": picked("other")}
    first = engine.next_question(V2, answers)
    for _ in range(500):
        assert engine.next_question(V2, answers) == first


def test_x_the_order_answers_were_given_in_changes_nothing():
    rng = random.Random(20260924)
    answers = {"current_problem.primary": WORDS, "symptom.onset.when": picked("today"),
               "symptom.duration": WORDS, "symptom.location": picked("chest"),
               "symptom.character": picked("pressure", "other"), "symptom.character.other": WORDS,
               "symptom.radiation": picked("yes")}
    expected = engine.resolve(V2, answers).states
    items = list(answers.items())
    for _ in range(200):
        rng.shuffle(items)
        assert engine.resolve(V2, dict(items)).states == expected


def test_x_resolution_reads_nothing_but_the_flow_and_the_answers():
    # No clock, no randomness, no I/O: the engine module imports none of them.
    import inspect

    source = inspect.getsource(engine)
    for forbidden in ("datetime", "time.", "random", "uuid", "requests", "httpx", "openai", "anthropic", "Session"):
        assert forbidden not in source, f"the engine must not depend on {forbidden}"


# --------------------------------------------------------------------------
# chains, declined triggers, revisions — on a flow built to have them
# --------------------------------------------------------------------------

YN = (Option("yes", "k.yes"), Option("no", "k.no"))
S = ConversationSection.LOCATION

CHAIN = FlowDefinition("chain", 1, (
    QuestionDefinition("a", 1, 10, S, ResponseType.YES_NO, "k.a", options=YN, required=False),
    QuestionDefinition("b", 1, 20, S, ResponseType.YES_NO, "k.b", options=YN,
                       branch=Branch("a_is_yes", "a", frozenset({"yes"}), "a_reported", "a_not_reported")),
    QuestionDefinition("c", 1, 30, S, ResponseType.FREE_TEXT, "k.c", required=False,
                       branch=Branch("b_is_yes", "b", frozenset({"yes"}), "b_reported", "b_not_reported")),
    QuestionDefinition("d", 1, 40, S, ResponseType.FREE_TEXT, "k.d"),
))


def test_a_declined_trigger_skips_its_follow_up_without_pretending_it_was_no():
    CHAIN.validate()
    r = engine.resolve(CHAIN, {"a": DECLINED})
    assert r.by_id["b"].status == Status.NOT_APPLICABLE
    assert r.by_id["b"].reason_code == TRIGGER_DECLINED


def test_a_follow_up_of_a_skipped_question_is_skipped_for_that_reason():
    r = engine.resolve(CHAIN, {"a": picked("no")})
    assert r.by_id["b"].reason_code == "a_not_reported"
    assert r.by_id["c"].reason_code == TRIGGER_NOT_APPLICABLE


def test_a_question_cannot_be_decided_before_its_trigger_is_answered():
    r = engine.resolve(CHAIN, {})
    assert r.by_id["b"].status == Status.UNDETERMINED
    assert r.by_id["c"].status == Status.UNDETERMINED
    assert r.next.question.id == "a"
    assert r.remaining == 2  # a and d are known to be left; b and c are not yet known


def test_revising_a_trigger_retires_every_answer_downstream_that_stops_applying():
    answers = {"a": picked("yes"), "b": picked("yes"), "c": WORDS, "d": WORDS}
    resolution, invalidated = engine.plan_revision(CHAIN, answers, "a", picked("no"))
    assert [s.question.id for s in invalidated] == ["b", "c"]
    assert [s.reason_code for s in invalidated] == ["a_not_reported", TRIGGER_NOT_APPLICABLE]
    # d did not depend on a, so it stands.
    assert resolution.by_id["d"].status == Status.ANSWERED


def test_revising_to_the_same_branch_retires_nothing():
    answers = {"a": picked("yes"), "b": picked("no"), "d": WORDS}
    _, invalidated = engine.plan_revision(CHAIN, answers, "b", picked("no"))
    assert invalidated == ()


def test_revising_open_a_branch_makes_its_follow_up_the_next_question():
    answers = {"a": picked("yes"), "b": picked("no"), "d": WORDS}
    resolution, invalidated = engine.plan_revision(CHAIN, answers, "b", picked("yes"))
    assert invalidated == ()
    assert resolution.next.question.id == "c"
    assert resolution.next.reason_code == "b_reported"


def test_engine_reason_codes_are_the_documented_four():
    assert ENGINE_REASON_CODES == {FLOW_SEQUENCE, FLOW_COMPLETE, TRIGGER_DECLINED, TRIGGER_NOT_APPLICABLE}
