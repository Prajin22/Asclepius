"""history_general v2 over HTTP: the new routes and the wire contract.

The service tests cover the machine. These check what a browser can send and
what it gets back — that a client cannot pick the tree or the next question,
that every payload says the flow is a draft, and that no wording travels.
"""

import uuid

from tests.conftest import API, auth

BASE = f"{API}/patients/me/conversations"


def _key() -> str:
    return uuid.uuid4().hex


def _body(q: dict, **overrides) -> dict:
    body = {"question_id": q["id"], "idempotency_key": _key()}
    if q["response_type"] == "free_text":
        body["text"] = "in my own words"
    elif q["response_type"] == "duration":
        body["value"] = {"duration": {"amount": 3, "unit": "days"}}
    else:
        body["value"] = {"choices": ["not_sure"]}
    return body | overrides


def _start(client, patient) -> dict:
    r = client.post(BASE, json={}, headers=patient.h)
    assert r.status_code == 201, r.text
    return r.json()


def _answer(client, patient, s, **overrides) -> dict:
    r = client.post(f"{BASE}/{s['id']}/answers", json=_body(s["question"], **overrides), headers=patient.h)
    assert r.status_code == 200, r.text
    return r.json()


def _to(client, patient, s, question_id, script=None) -> dict:
    script = script or {}
    while s["question"] is not None and s["question"]["id"] != question_id:
        s = _answer(client, patient, s, **script.get(s["question"]["id"], {}))
    return s


def test_a_new_conversation_says_it_is_an_engineering_draft(client, make_patient):
    s = _start(client, make_patient())
    assert (s["flow_id"], s["flow_version"]) == ("history_general", 2)
    assert (s["flow_status"], s["clinical_review"]) == ("engineering_draft", "required")
    assert s["current_step"] == "current_problem.primary"
    assert s["question"]["reason"] == {"code": "flow_sequence", "trigger_question_id": None, "predicate_id": None}


def test_a_client_cannot_choose_the_flow_version(client, make_patient):
    patient = make_patient()
    r = client.post(BASE, json={"flow_version": 1}, headers=patient.h)
    assert r.status_code == 422
    r = client.post(BASE, json={"flow_id": "something_else"}, headers=patient.h)
    assert r.status_code == 422


def test_a_client_cannot_name_the_next_question(client, make_patient):
    patient = make_patient()
    s = _start(client, patient)
    r = client.post(f"{BASE}/{s['id']}/answers",
                    json=_body(s["question"], next_question_id="allergies.details"), headers=patient.h)
    assert r.status_code == 422


def test_options_travel_as_ids_and_keys_with_their_exclusive_flag(client, make_patient):
    patient = make_patient()
    s = _to(client, patient, _start(client, patient), "symptom.associated")
    options = {o["id"]: o for o in s["question"]["options"]}
    assert options["none_of_these"] == {
        "id": "none_of_these", "label_key": "conversation.choice.common.none_of_these", "exclusive": True}
    assert options["fever"]["exclusive"] is False
    assert s["question"]["prompt_key"] == "conversation.question.symptom.associated.v2"


def test_a_branch_arrives_with_its_reason_and_trigger(client, make_patient):
    patient = make_patient()
    s = _to(client, patient, _start(client, patient), "symptom.radiation")
    s = _answer(client, patient, s, value={"choices": ["yes"]})
    assert s["question"]["id"] == "symptom.radiation.location"
    assert s["question"]["reason"] == {
        "code": "radiation_reported", "trigger_question_id": "symptom.radiation", "predicate_id": "radiation_is_yes"}


def test_declining_is_explicit_and_refused_on_a_required_question(client, make_patient):
    patient = make_patient()
    s = _to(client, patient, _start(client, patient), "symptom.location")
    r = client.post(f"{BASE}/{s['id']}/answers",
                    json={"question_id": "symptom.location", "idempotency_key": _key(), "declined": True},
                    headers=patient.h)
    assert r.status_code == 422
    assert r.json()["code"] == "answer_required"


def test_the_old_skipped_field_is_gone(client, make_patient):
    patient = make_patient()
    s = _start(client, patient)
    r = client.post(f"{BASE}/{s['id']}/answers", json=_body(s["question"], skipped=True), headers=patient.h)
    assert r.status_code == 422


def test_review_over_http_lists_every_outcome_and_changes_nothing(client, make_patient):
    patient = make_patient()
    s = _start(client, patient)
    s = _to(client, patient, s, None, {
        "symptom.radiation": {"value": {"choices": ["no"]}},
        "allergies.known": {"value": {"choices": ["yes"]}},
        "allergies.details": {"declined": True, "text": None},
    })
    before = client.get(f"{BASE}/{s['id']}", headers=patient.h).json()

    r = client.get(f"{BASE}/{s['id']}/review", headers=patient.h)
    assert r.status_code == 200, r.text
    review = r.json()
    assert review["can_complete"] is True
    assert review["conversation"]["current_step"] == "review.confirm"
    assert review["conversation"]["flow_status"] == "engineering_draft"
    outcome = {i["question_id"]: i for i in review["items"]}
    assert outcome["symptom.radiation.location"]["outcome"] == "not_applicable"
    assert outcome["symptom.radiation.location"]["reason"]["code"] == "radiation_not_reported"
    assert outcome["allergies.details"]["outcome"] == "declined"
    assert outcome["current_problem.primary"]["response"]["answer_text"] == "in my own words"
    symptom = next(c for c in review["candidates"] if c["category"] == "symptom")
    assert (symptom["review_state"], symptom["becomes"]) == ("pending", None)
    assert review["counts"]["candidates_pending"] == 1

    assert client.get(f"{BASE}/{s['id']}", headers=patient.h).json() == before


def test_revision_over_http_keeps_the_old_answer_and_opens_the_branch(client, make_patient):
    patient = make_patient()
    s = _to(client, patient, _start(client, patient), None, {"symptom.radiation": {"value": {"choices": ["no"]}}})
    assert s["current_step"] == "review.confirm"

    r = client.post(f"{BASE}/{s['id']}/answers/symptom.radiation/revision",
                    json={"idempotency_key": _key(), "value": {"choices": ["yes"]},
                          "expected_revision": s["revision"]},
                    headers=patient.h)
    assert r.status_code == 200, r.text
    revised = r.json()
    assert revised["status"] == "awaiting_answer"
    assert revised["question"]["id"] == "symptom.radiation.location"
    current = [x for x in revised["responses"] if x["question_id"] == "symptom.radiation"]
    assert [x["answer_value"]["choices"] for x in current] == [["yes"]]  # only the current one is listed


def test_revising_a_question_that_was_not_asked_is_refused(client, make_patient):
    patient = make_patient()
    s = _to(client, patient, _start(client, patient), None)
    r = client.post(f"{BASE}/{s['id']}/answers/symptom.radiation.location/revision",
                    json={"idempotency_key": _key(), "text": "my arm"}, headers=patient.h)
    assert r.status_code == 409
    assert r.json()["code"] == "question_not_answered"


def test_a_stale_revision_is_refused(client, make_patient):
    patient = make_patient()
    s = _to(client, patient, _start(client, patient), "symptom.location")
    stale = s["revision"] - 1
    r = client.post(f"{BASE}/{s['id']}/answers/current_problem.primary/revision",
                    json={"idempotency_key": _key(), "text": "changed", "expected_revision": stale},
                    headers=patient.h)
    assert r.status_code == 409
    assert r.json()["code"] == "conversation_out_of_date"


def test_no_route_creates_a_candidate_directly(client, make_patient):
    patient = make_patient()
    s = _start(client, patient)
    for method, url in (("post", f"{BASE}/{s['id']}/candidates"), ("put", f"{BASE}/{s['id']}/candidates")):
        r = getattr(client, method)(url, json={"category": "allergy", "value": "penicillin"}, headers=patient.h)
        assert r.status_code in (404, 405)


def test_another_patient_cannot_review_or_revise(client, make_patient):
    patient = make_patient()
    s = _to(client, patient, _start(client, patient), "symptom.location")
    intruder = make_patient(email="intruder@example.com", name="Someone Else")
    assert client.get(f"{BASE}/{s['id']}/review", headers=intruder.h).status_code == 404
    r = client.post(f"{BASE}/{s['id']}/answers/current_problem.primary/revision",
                    json={"idempotency_key": _key(), "text": "hijacked"}, headers=intruder.h)
    assert r.status_code == 404


def test_a_doctor_cannot_reach_review_or_revision(client, make_patient, make_doctor):
    patient = make_patient()
    s = _to(client, patient, _start(client, patient), "symptom.location")
    doctor = make_doctor()
    assert client.get(f"{BASE}/{s['id']}/review", headers=auth(doctor.token)).status_code in (403, 404)
    r = client.post(f"{BASE}/{s['id']}/answers/current_problem.primary/revision",
                    json={"idempotency_key": _key(), "text": "x"}, headers=auth(doctor.token))
    assert r.status_code in (403, 404)


def test_nothing_in_a_v2_conversation_can_express_a_clinical_conclusion(client, make_patient):
    patient = make_patient()
    s = _to(client, patient, _start(client, patient), None, {
        "symptom.radiation": {"value": {"choices": ["yes"]}},
        "symptom.associated": {"value": {"choices": ["fever", "other"]}},
    })
    review = client.get(f"{BASE}/{s['id']}/review", headers=patient.h).json()
    flat = (str(s) + str(review)).lower()
    for forbidden in ("diagnos", "differential", "severity", "triage", "risk_score", "urgency", "red_flag"):
        assert forbidden not in flat
