"""The history conversation over HTTP.

The domain tests cover the state machine. These cover the surface: what a
client may send, what it gets back, and what it is refused. The recurring
question is whether a client can steer the conversation — it must not be able
to.
"""

import uuid

import pytest

from app.conversation import flow
from tests.conftest import API, auth


@pytest.fixture(autouse=True)
def _history_general_v1(monkeypatch):
    """These tests exercise history_general v1 over HTTP; v1 stays supported for
    every session started under it. v2 has its own tests."""
    monkeypatch.setattr(flow, "FLOW_VERSION", 1)


def _key() -> str:
    return uuid.uuid4().hex


def _start(client, patient, language: str | None = None):
    body = {"language": language} if language else {}
    r = client.post(f"{API}/patients/me/conversations", json=body, headers=patient.h)
    assert r.status_code == 201, r.text
    return r.json()


def _answer_body(question: dict, **overrides) -> dict:
    body = {"question_id": question["id"], "idempotency_key": _key()}
    kind = question["response_type"]
    if kind == "free_text":
        body["text"] = f"an answer to {question['id']}"
    elif kind == "duration":
        body["value"] = {"duration": {"amount": 3, "unit": "days"}}
    else:
        body["value"] = {"choices": [question["options"][0]["id"]]}
    return body | overrides


def _answer(client, patient, session, **overrides):
    r = client.post(
        f"{API}/patients/me/conversations/{session['id']}/answers",
        json=_answer_body(session["question"], **overrides),
        headers=patient.h,
    )
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------------------------------------------------------
# starting and reading
# --------------------------------------------------------------------------


def test_starting_returns_the_first_question_with_its_localisation_key(client, make_patient):
    patient = make_patient()
    body = _start(client, patient)

    question = body["question"]
    assert question["id"] == "problem.description"
    assert question["prompt_key"].startswith("conversation.q.")
    assert body["status"] == "awaiting_answer"
    assert body["answered"] == 0
    assert body["remaining"] > 0


def test_question_text_never_crosses_the_wire(client, make_patient):
    patient = make_patient()
    session = _start(client, patient)

    # Only keys travel, so translating a question cannot rewrite what a patient
    # is recorded as having been shown.
    for _ in range(4):
        question = session["question"]
        # Every field that would carry wording is a localisation key instead.
        assert question["prompt_key"].startswith("conversation.")
        assert question["help_key"] is None or question["help_key"].startswith("conversation.")
        assert not {k for k in question if k in ("prompt", "text", "label", "title")}
        for option in question.get("options", []):
            # `exclusive` is a flag, not wording; nothing here is text to show.
            assert set(option) == {"id", "label_key", "exclusive"}
            assert option["label_key"].startswith("conversation.")
        session = _answer(client, patient, session)


def test_the_conversation_in_progress_can_be_fetched_back(client, make_patient):
    patient = make_patient()
    session = _start(client, patient)
    _answer(client, patient, session)

    r = client.get(f"{API}/patients/me/conversations/current", headers=patient.h)

    assert r.status_code == 200
    assert r.json()["id"] == session["id"]
    assert r.json()["answered"] == 1


def test_no_conversation_in_progress_is_a_clean_404(client, make_patient):
    patient = make_patient()
    r = client.get(f"{API}/patients/me/conversations/current", headers=patient.h)
    assert r.status_code == 404


def test_starting_again_returns_the_same_conversation(client, make_patient):
    patient = make_patient()
    first = _start(client, patient)
    _answer(client, patient, first)

    second = _start(client, patient)

    assert second["id"] == first["id"]
    assert second["answered"] == 1


def test_the_language_defaults_to_the_patients_own(client, make_patient):
    patient = make_patient(lang="ta")
    assert _start(client, patient)["language"] == "ta"


# --------------------------------------------------------------------------
# a client cannot steer the conversation
# --------------------------------------------------------------------------


def test_no_route_accepts_a_next_question(client, make_patient):
    patient = make_patient()
    session = _start(client, patient)

    r = client.post(
        f"{API}/patients/me/conversations/{session['id']}/answers",
        json={
            "question_id": "problem.description",
            "idempotency_key": _key(),
            "text": "headache",
            "next_question_id": "allergy.which",
        },
        headers=patient.h,
    )

    # The field does not exist, and unknown fields are refused outright.
    assert r.status_code == 422


def test_answering_a_question_that_was_not_asked_is_refused(client, make_patient):
    patient = make_patient()
    session = _start(client, patient)

    r = client.post(
        f"{API}/patients/me/conversations/{session['id']}/answers",
        json={
            "question_id": "allergy.which",
            "idempotency_key": _key(),
            "text": "penicillin",
        },
        headers=patient.h,
    )

    assert r.status_code == 409
    assert r.json()["code"] == "unexpected_question"


def test_an_option_that_was_not_offered_is_refused(client, make_patient):
    patient = make_patient()
    session = _start(client, patient)
    session = _answer(client, patient, session)  # problem
    session = _answer(client, patient, session)  # duration
    session = _answer(client, patient, session)  # happened before
    assert session["question"]["id"] == "symptom.is_pain"

    r = client.post(
        f"{API}/patients/me/conversations/{session['id']}/answers",
        json={
            "question_id": "symptom.is_pain",
            "idempotency_key": _key(),
            "value": {"choices": ["definitely_cancer"]},
        },
        headers=patient.h,
    )

    assert r.status_code == 422


def test_arbitrary_json_cannot_be_written_into_an_answer(client, make_patient):
    patient = make_patient()
    session = _start(client, patient)

    r = client.post(
        f"{API}/patients/me/conversations/{session['id']}/answers",
        json={
            "question_id": "problem.description",
            "idempotency_key": _key(),
            "text": "headache",
            "value": {"diagnosis": "migraine", "severity": 9},
        },
        headers=patient.h,
    )

    assert r.status_code == 422


def test_an_answer_longer_than_the_limit_is_refused_not_truncated(client, make_patient):
    patient = make_patient()
    session = _start(client, patient)

    r = client.post(
        f"{API}/patients/me/conversations/{session['id']}/answers",
        json={
            "question_id": "problem.description",
            "idempotency_key": _key(),
            "text": "x" * 2001,
        },
        headers=patient.h,
    )

    # Quietly dropping the end of what someone typed about their health would
    # be worse than telling them it was too long.
    assert r.status_code == 422


# --------------------------------------------------------------------------
# idempotency and concurrency
# --------------------------------------------------------------------------


def test_the_same_request_twice_produces_one_answer(client, make_patient):
    patient = make_patient()
    session = _start(client, patient)
    body = _answer_body(session["question"])
    url = f"{API}/patients/me/conversations/{session['id']}/answers"

    first = client.post(url, json=body, headers=patient.h)
    second = client.post(url, json=body, headers=patient.h)

    assert first.status_code == second.status_code == 200
    assert first.json()["answered"] == second.json()["answered"] == 1
    assert len(second.json()["responses"]) == 1
    assert second.json()["revision"] == first.json()["revision"]
    assert second.json()["question"]["id"] == first.json()["question"]["id"]


def test_an_answer_built_against_a_stale_revision_is_refused(client, make_patient):
    patient = make_patient()
    session = _start(client, patient)
    stale = session["revision"]
    session = _answer(client, patient, session)

    r = client.post(
        f"{API}/patients/me/conversations/{session['id']}/answers",
        json=_answer_body(session["question"], expected_revision=stale),
        headers=patient.h,
    )

    assert r.status_code == 409
    assert r.json()["code"] == "conversation_out_of_date"


# --------------------------------------------------------------------------
# who may reach a conversation
# --------------------------------------------------------------------------


def test_another_patient_cannot_see_or_answer_a_conversation(client, make_patient):
    patient = make_patient()
    session = _start(client, patient)
    intruder = make_patient(email="intruder@example.com", name="Someone Else")

    assert client.get(
        f"{API}/patients/me/conversations/{session['id']}", headers=intruder.h
    ).status_code == 404
    assert client.post(
        f"{API}/patients/me/conversations/{session['id']}/answers",
        json=_answer_body(session["question"]),
        headers=intruder.h,
    ).status_code == 404


def test_a_doctor_cannot_reach_a_patients_conversation(client, make_patient, make_doctor):
    patient = make_patient()
    session = _start(client, patient)
    doctor = make_doctor()

    # A conversation reaches a clinician only through confirmed, shared records.
    for url in (
        f"{API}/patients/me/conversations/current",
        f"{API}/patients/me/conversations/{session['id']}",
    ):
        assert client.get(url, headers=auth(doctor.token)).status_code in (403, 404)


def test_a_conversation_needs_a_signed_in_patient(client, make_patient):
    patient = make_patient()
    session = _start(client, patient)

    assert client.get(f"{API}/patients/me/conversations/{session['id']}").status_code == 401
    assert client.post(f"{API}/patients/me/conversations", json={}).status_code == 401


def test_a_candidate_from_another_conversation_is_not_found(client, make_patient):
    patient = make_patient()
    session = _answer(client, patient, _start(client, patient))
    candidate = session["candidates"][0]

    r = client.post(
        f"{API}/patients/me/conversations/{uuid.uuid4()}/candidates/{candidate['id']}",
        json={"action": "confirm"},
        headers=patient.h,
    )

    assert r.status_code == 404


# --------------------------------------------------------------------------
# review, pause, completion
# --------------------------------------------------------------------------


def test_a_candidate_is_pending_until_the_patient_acts_on_it(client, make_patient):
    patient = make_patient()
    session = _answer(client, patient, _start(client, patient), text="my chest hurts")

    candidate = session["candidates"][0]
    assert candidate["review_state"] == "pending"
    assert candidate["original_text"] == "my chest hurts"
    assert candidate["medical_record_id"] is None
    assert client.get(f"{API}/patients/me/records", headers=patient.h).json() == []


def test_confirming_a_candidate_is_visible_in_the_patients_records(client, make_patient):
    patient = make_patient()
    session = _start(client, patient)
    while session["question"] is not None:
        session = _answer(client, patient, session)

    allergy = next(c for c in session["candidates"] if c["category"] == "allergy")
    r = client.post(
        f"{API}/patients/me/conversations/{session['id']}/candidates/{allergy['id']}",
        json={"action": "confirm"},
        headers=patient.h,
    )

    assert r.status_code == 200
    assert r.json()["review_state"] == "confirmed"
    records = client.get(f"{API}/patients/me/records", headers=patient.h).json()
    assert any(rec["type"] == "allergy" and rec["source"] == "patient" for rec in records)


def test_editing_a_candidate_requires_a_value(client, make_patient):
    patient = make_patient()
    session = _answer(client, patient, _start(client, patient))
    candidate = session["candidates"][0]

    r = client.post(
        f"{API}/patients/me/conversations/{session['id']}/candidates/{candidate['id']}",
        json={"action": "edit"},
        headers=patient.h,
    )

    assert r.status_code == 422


def test_an_unknown_review_action_is_refused(client, make_patient):
    patient = make_patient()
    session = _answer(client, patient, _start(client, patient))
    candidate = session["candidates"][0]

    r = client.post(
        f"{API}/patients/me/conversations/{session['id']}/candidates/{candidate['id']}",
        json={"action": "diagnose"},
        headers=patient.h,
    )

    assert r.status_code == 422


def test_pausing_and_resuming_over_http(client, make_patient):
    patient = make_patient()
    session = _answer(client, patient, _start(client, patient))
    waiting_on = session["question"]["id"]
    url = f"{API}/patients/me/conversations/{session['id']}"

    paused = client.post(f"{url}/pause", headers=patient.h)
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    # A paused conversation does not take answers.
    assert client.post(
        f"{url}/answers", json=_answer_body(session["question"]), headers=patient.h
    ).status_code == 409

    resumed = client.post(f"{url}/resume", headers=patient.h)
    assert resumed.status_code == 200
    assert resumed.json()["question"]["id"] == waiting_on


def test_completing_a_conversation_over_http(client, make_patient):
    patient = make_patient()
    session = _start(client, patient)
    url = f"{API}/patients/me/conversations/{session['id']}"

    # Cannot finish while questions remain.
    assert client.post(f"{url}/complete", headers=patient.h).status_code == 409

    while session["question"] is not None:
        session = _answer(client, patient, session)
    assert session["status"] == "awaiting_confirmation"

    done = client.post(f"{url}/complete", headers=patient.h)
    assert done.status_code == 200
    assert done.json()["status"] == "completed"
    assert done.json()["remaining"] == 0


def test_nothing_in_the_payload_can_express_a_clinical_conclusion(client, make_patient):
    patient = make_patient()
    session = _start(client, patient)
    while session["question"] is not None:
        session = _answer(client, patient, session)

    flat = str(session).lower()
    for forbidden in ("diagnosis", "differential", "severity", "triage", "risk_score", "urgency"):
        assert forbidden not in flat


def test_why_a_question_was_asked_travels_as_a_key_not_english(client, make_patient):
    patient = make_patient(lang="ta")
    session = _start(client, patient)

    # An always-asked question needs no explanation.
    assert session["question"]["reason"] == {
        "code": "flow_sequence", "trigger_question_id": None, "predicate_id": None,
    }

    session = _answer(client, patient, session)  # problem
    session = _answer(client, patient, session)  # duration
    session = _answer(client, patient, session)  # happened before
    session = _answer(client, patient, session)  # is_pain -> "yes"

    # A conditional one explains itself, in a form the browser can translate.
    assert session["question"]["id"] == "symptom.site"
    assert session["question"]["reason"] == {
        "code": "pain_reported",
        "trigger_question_id": "symptom.is_pain",
        "predicate_id": "is_pain_is_yes",
    }

    # The English sentence stays on the server. Nothing in the payload is prose.
    assert "the patient said" not in str(session).lower()
