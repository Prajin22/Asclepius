"""The curator workflow: who may do what, and what each step does (Phase 2).

    draft → under_review → approved | rejected       (sources and versions alike)

Nothing is approved by anything but an explicit approval naming the checksum
the curator reviewed; a version needs an approved source first; approved and
rejected records are final, and an attempt to change one is refused and
audited; versions accumulate rather than overwrite; status history only grows.
"""

import uuid

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.models import AuditEvent, CorpusDocument, Instrument, ProvisionVersion
from app.models.enums import UserRole
from app.sakti import seed as sakti_seed
from tests.conftest import API
from tests.corpus_fixtures import (  # noqa: F401  (fixtures)
    ALPHA,
    BETA,
    DELTA,
    PAGE_ONE,
    PAGE_TWO,
    REVISED_BETA,
    REVISED_PAGE_ONE,
    Corpus,
    corpus,
    curator,
    expected_text,
    sakti,
    sakti_account,
    sha256,
)

# --------------------------------------------------------------------------
# Authorisation
# --------------------------------------------------------------------------

#: Every corpus endpoint that changes anything. {id} is filled with a real record.
MUTATIONS = [
    ("post", "/instruments", "json"),
    ("post", "/instruments/{instrument}/provisions", "json"),
    ("post", "/sources", "form"),
    ("post", "/sources/{source}/parse", None),
    ("post", "/sources/{source}/submit", None),
    ("post", "/sources/{source}/approve", "json"),
    ("post", "/sources/{source}/reject", "json"),
    ("post", "/sources/{source}/versions", "json"),
    ("patch", "/versions/{version}", "json"),
    ("post", "/versions/{version}/submit", None),
    ("post", "/versions/{version}/approve", "json"),
    ("post", "/versions/{version}/reject", "json"),
    ("post", "/versions/{version}/status-events", "json"),
]
READS = ["/authorities", "/instruments", "/instruments/{instrument}", "/sources", "/sources/{source}",
         "/sources/{source}/text", "/sources/{source}/diff", "/sources/{source}/original", "/versions/{version}",
         "/versions/{version}/diff", "/review-queue", "/drafts"]


@pytest.fixture
def records(corpus):
    instrument = corpus.instrument()
    source = corpus.source(instrument)
    provision = corpus.provision(instrument)
    version = corpus.version(source, provision).json()
    return {"instrument": instrument["id"], "source": source["id"], "version": version["id"]}


def _call(client, headers, method, path, kind):
    kwargs = {"json": {}} if kind == "json" else {"data": {}} if kind == "form" else {}
    return getattr(client, method)(f"{API}/corpus{path}", headers=headers, **kwargs)


@pytest.mark.parametrize("role", [UserRole.USER, UserRole.FACILITATOR, UserRole.ADMIN])
@pytest.mark.parametrize("method,path,kind", MUTATIONS)
def test_only_a_curator_may_change_the_corpus(sakti, sakti_account, records, role, method, path, kind):
    other = sakti_account(role)
    r = _call(sakti, other.h, method, path.format(**records), kind)
    assert r.status_code == 403, f"{role} reached {method.upper()} {path}"


@pytest.mark.parametrize("method,path,kind", MUTATIONS)
def test_nobody_signed_out_reaches_the_corpus(sakti, records, method, path, kind):
    assert _call(sakti, {}, method, path.format(**records), kind).status_code == 401


@pytest.mark.parametrize("path", READS)
def test_an_administrator_may_read_the_corpus_for_oversight(sakti, sakti_account, records, path):
    admin = sakti_account(UserRole.ADMIN)
    assert sakti.get(f"{API}/corpus{path.format(**records)}", headers=admin.h).status_code == 200


@pytest.mark.parametrize("role", [UserRole.USER, UserRole.FACILITATOR])
@pytest.mark.parametrize("path", READS)
def test_users_and_facilitators_cannot_read_unapproved_corpus(sakti, sakti_account, records, role, path):
    other = sakti_account(role)
    assert sakti.get(f"{API}/corpus{path.format(**records)}", headers=other.h).status_code == 403


def test_an_instrument_is_not_created_twice_in_a_lane(corpus):
    corpus.instrument(title="Same title")
    r = corpus.post("/instruments", json={"lane": "india", "instrument_type": "other", "title": "Same title",
                                          "issued_by": "The test suite"})
    assert r.status_code == 409 and r.json()["code"] == "instrument_exists"
    assert corpus.instrument(lane="international", title="Same title")["lane"] == "international"


def test_carebridge_has_no_corpus(client):
    for path in ("/corpus/sources", "/corpus/instruments", "/corpus/authorities"):
        assert client.get(f"{API}{path}").status_code == 404


def test_the_seed_creates_no_corpus(db):
    sakti_seed.seed(db)
    for model in (Instrument, CorpusDocument, ProvisionVersion):
        assert db.scalar(select(func.count()).select_from(model)) == 0


# --------------------------------------------------------------------------
# The state machine
# --------------------------------------------------------------------------


def test_the_curator_takes_a_source_and_a_version_from_draft_to_approved(corpus, curator):
    instrument = corpus.instrument()
    source = corpus.source(instrument)
    assert source["review_state"] == "draft"
    submitted = corpus.submit_source(source)
    assert submitted["review_state"] == "under_review" and submitted["submitted_at"]
    r = corpus.post(f"/sources/{source['id']}/approve", json={"expected_sha256": source["sha256"]})
    approved = r.json()
    assert approved["review_state"] == "approved"
    assert approved["approved_by"]["email"] == curator.email and approved["approved_at"]

    provision = corpus.provision(instrument)
    version = corpus.version(source, provision).json()
    assert version["review_state"] == "draft"
    done = corpus.approve_version(version)
    assert done["review_state"] == "approved" and done["approved_by"]["email"] == curator.email


@pytest.mark.parametrize("action,body", [("approve", "sha"), ("reject", {"reason": "x"})])
def test_a_draft_cannot_skip_review(corpus, action, body):
    source = corpus.source()
    payload = {"expected_sha256": source["sha256"]} if body == "sha" else body
    r = corpus.post(f"/sources/{source['id']}/{action}", json=payload)
    assert r.status_code == 409 and r.json()["code"] == "invalid_transition"


def test_a_source_under_review_cannot_be_submitted_again(corpus):
    source = corpus.source()
    corpus.submit_source(source)
    r = corpus.post(f"/sources/{source['id']}/submit")
    assert r.status_code == 409 and r.json()["code"] == "invalid_transition"


@pytest.mark.parametrize("action", ["submit", "approve", "reject", "parse"])
def test_an_approved_source_is_final_and_the_attempt_is_recorded(db, corpus, action):
    source = corpus.approve_source(corpus.source())
    payload = {"expected_sha256": source["sha256"]} if action == "approve" else {"reason": "x"}
    r = corpus.post(f"/sources/{source['id']}/{action}", json=payload if action in ("approve", "reject") else None)
    assert r.status_code == 409 and r.json()["code"] == "corpus_record_final"
    refused = db.scalars(select(AuditEvent).where(AuditEvent.action == "corpus.mutation_refused")).all()
    assert [(e.resource_id, e.details["attempted"]) for e in refused] == [(source["id"], action)]


def test_approval_names_the_file_that_was_reviewed(corpus):
    source = corpus.source()
    corpus.submit_source(source)
    r = corpus.post(f"/sources/{source['id']}/approve", json={"expected_sha256": "0" * 64})
    assert r.status_code == 409 and r.json()["code"] == "checksum_mismatch"
    r = corpus.post(f"/sources/{source['id']}/approve", json={"expected_sha256": "not-a-checksum"})
    assert r.status_code == 422


def test_a_rejected_source_never_becomes_authoritative_and_takes_its_drafts_with_it(corpus):
    instrument = corpus.instrument()
    source = corpus.source(instrument)
    provision = corpus.provision(instrument)
    draft = corpus.version(source, provision).json()
    corpus.submit_source(source)
    r = corpus.post(f"/sources/{source['id']}/reject", json={"reason": "Not the official copy"})
    assert r.json()["review_state"] == "rejected" and r.json()["rejection_reason"] == "Not the official copy"
    assert corpus.get(f"/versions/{draft['id']}").json()["review_state"] == "rejected"
    assert corpus.get("/sources", params={"review_state": "approved"}).json() == []
    r = corpus.version(source, provision, BETA)
    assert r.status_code == 409 and r.json()["code"] == "source_rejected"
    r = corpus.post(f"/sources/{source['id']}/submit")
    assert r.status_code == 409 and r.json()["code"] == "corpus_record_final"


def test_a_rejection_needs_a_reason(corpus):
    source = corpus.source()
    corpus.submit_source(source)
    assert corpus.post(f"/sources/{source['id']}/reject", json={"reason": "  "}).status_code == 422


def test_by_default_one_curator_may_run_the_whole_workflow(corpus):
    # Until a legal reviewer is named (plan Q7), one curator can do everything.
    assert get_settings().corpus_separate_approver is False
    assert corpus.approved().version["review_state"] == "approved"


def test_with_a_separate_approver_required_nobody_approves_their_own_work(sakti, sakti_account, corpus, monkeypatch):
    monkeypatch.setattr(get_settings(), "corpus_separate_approver", True)
    second = Corpus(sakti, sakti_account(UserRole.CURATOR, "second@sakti.example.com").h)
    instrument = corpus.instrument()
    source = corpus.source(instrument)
    corpus.submit_source(source)
    r = corpus.post(f"/sources/{source['id']}/approve", json={"expected_sha256": source["sha256"]})
    assert r.status_code == 409 and r.json()["code"] == "approver_must_differ"
    r = second.post(f"/sources/{source['id']}/approve", json={"expected_sha256": source["sha256"]})
    assert r.status_code == 200 and r.json()["approved_by"]["email"] == "second@sakti.example.com"

    version = corpus.version(source, corpus.provision(instrument)).json()
    corpus.post(f"/versions/{version['id']}/submit")
    r = corpus.post(f"/versions/{version['id']}/approve", json={"expected_text_sha256": version["text_sha256"]})
    assert r.status_code == 409 and r.json()["code"] == "approver_must_differ"
    r = second.post(f"/versions/{version['id']}/approve", json={"expected_text_sha256": version["text_sha256"]})
    assert r.status_code == 200


# --------------------------------------------------------------------------
# Versions: exact text, approval order, immutability
# --------------------------------------------------------------------------


def test_a_version_is_the_exact_text_of_its_span(corpus):
    instrument = corpus.instrument()
    source = corpus.source(instrument)
    provision = corpus.provision(instrument, locator="Delta")
    version = corpus.version(source, provision, DELTA).json()
    assert version["text"] == DELTA
    assert version["text_sha256"] == sha256(DELTA)
    document = expected_text([PAGE_ONE, PAGE_TWO])
    assert document[version["char_start"]:version["char_end"]] == DELTA
    assert (version["page_start"], version["page_end"]) == (2, 2)
    assert version["ocr_derived"] is False and version["lane"] == "india"
    assert version["source"]["id"] == source["id"] and version["provision"]["locator"] == "Delta"


def test_a_version_may_span_pages_and_keeps_the_page_break(corpus):
    instrument = corpus.instrument()
    source = corpus.source(instrument)
    provision = corpus.provision(instrument)
    start, _ = corpus.span(source, PAGE_ONE[-1])
    _, end = corpus.span(source, DELTA)
    version = corpus.post(f"/sources/{source['id']}/versions",
                          json={"provision_id": provision["id"], "char_start": start, "char_end": end}).json()
    assert version["text"] == f"{PAGE_ONE[-1]}\f{PAGE_TWO[0]}\n{DELTA}"
    assert (version["page_start"], version["page_end"]) == (1, 2)


@pytest.mark.parametrize("start,end,code", [(0, 10 ** 6, "span_out_of_range"), (50, 40, None)])
def test_a_span_must_lie_inside_the_text(corpus, start, end, code):
    instrument = corpus.instrument()
    source = corpus.source(instrument)
    r = corpus.post(f"/sources/{source['id']}/versions",
                    json={"provision_id": corpus.provision(instrument)["id"], "char_start": start, "char_end": end})
    assert r.status_code == 422
    if code:
        assert r.json()["code"] == code


def test_a_span_of_nothing_but_whitespace_is_refused(corpus):
    instrument = corpus.instrument()
    source = corpus.source(instrument)
    start, end = corpus.span(source, ALPHA)
    r = corpus.post(f"/sources/{source['id']}/versions",
                    json={"provision_id": corpus.provision(instrument)["id"], "char_start": end, "char_end": end + 1})
    assert r.status_code == 422 and r.json()["code"] == "span_empty"


def test_no_request_can_carry_legal_text(corpus):
    instrument = corpus.instrument()
    source = corpus.source(instrument)
    start, end = corpus.span(source, ALPHA)
    r = corpus.post(f"/sources/{source['id']}/versions",
                    json={"provision_id": corpus.provision(instrument)["id"], "char_start": start, "char_end": end,
                          "text": "Words typed by hand"})
    assert r.status_code == 422  # unknown field: text only ever comes from the source


def test_a_version_needs_its_source_approved_first(corpus):
    instrument = corpus.instrument()
    source = corpus.source(instrument)
    version = corpus.version(source, corpus.provision(instrument)).json()
    assert corpus.post(f"/versions/{version['id']}/submit").status_code == 200
    r = corpus.post(f"/versions/{version['id']}/approve", json={"expected_text_sha256": version["text_sha256"]})
    assert r.status_code == 409 and r.json()["code"] == "source_not_approved"


def test_approval_names_the_text_that_was_reviewed(corpus):
    instrument = corpus.instrument()
    source = corpus.approve_source(corpus.source(instrument))
    version = corpus.version(source, corpus.provision(instrument)).json()
    corpus.post(f"/versions/{version['id']}/submit")
    r = corpus.post(f"/versions/{version['id']}/approve", json={"expected_text_sha256": sha256("other text")})
    assert r.status_code == 409 and r.json()["code"] == "checksum_mismatch"


def test_a_draft_can_be_adjusted_and_the_text_follows_the_span(corpus):
    instrument = corpus.instrument()
    source = corpus.source(instrument)
    version = corpus.version(source, corpus.provision(instrument)).json()
    start, end = corpus.span(source, BETA)
    r = corpus.patch(f"/versions/{version['id']}",
                     json={"char_start": start, "char_end": end, "valid_from": "2020-01-01"})
    assert r.status_code == 200
    assert r.json()["text"] == BETA and r.json()["valid_from"] == "2020-01-01"
    r = corpus.patch(f"/versions/{version['id']}", json={"valid_from": None})
    assert r.json()["valid_from"] is None


def test_a_version_under_review_is_not_edited(corpus):
    instrument = corpus.instrument()
    version = corpus.version(corpus.source(instrument), corpus.provision(instrument)).json()
    corpus.post(f"/versions/{version['id']}/submit")
    r = corpus.patch(f"/versions/{version['id']}", json={"valid_to": "2030-01-01"})
    assert r.status_code == 409 and r.json()["code"] == "version_not_editable"


def test_approved_text_cannot_be_changed_through_the_api_and_the_attempt_is_recorded(db, corpus):
    done = corpus.approved()
    for body in ({"char_end": done.version["char_end"] - 3}, {"valid_to": "2030-01-01"}):
        r = corpus.patch(f"/versions/{done.version['id']}", json=body)
        assert r.status_code == 409 and r.json()["code"] == "corpus_record_final"
    after = corpus.get(f"/versions/{done.version['id']}").json()
    assert after["text"] == ALPHA and after["text_sha256"] == sha256(ALPHA) and after["valid_to"] is None
    refused = db.scalar(select(func.count()).select_from(AuditEvent).where(
        AuditEvent.action == "corpus.mutation_refused", AuditEvent.resource_id == done.version["id"]))
    assert refused == 2


def test_a_new_version_never_overwrites_the_old_one(corpus):
    first = corpus.approved(BETA)
    revised = corpus.approve_source(corpus.source(first.instrument, pages=[REVISED_PAGE_ONE, PAGE_TWO]))
    second = corpus.version(revised, first.provision, REVISED_BETA, valid_from="2026-01-01").json()
    second = corpus.approve_version(second)

    versions = corpus.get(f"/instruments/{first.instrument['id']}").json()["provisions"][0]["versions"]
    assert [(v["version_number"], v["review_state"]) for v in versions] == [(1, "approved"), (2, "approved")]
    old = corpus.get(f"/versions/{first.version['id']}").json()
    assert old["text"] == BETA and old["source"]["id"] == first.source["id"]
    assert second["text"] == REVISED_BETA

    diff = corpus.get(f"/versions/{second['id']}/diff").json()
    assert diff["baseline"]["id"] == first.version["id"] and diff["baseline"]["label"] == "v1"
    replace = diff["blocks"][0]
    assert replace["op"] == "replace" and replace["old"] == [BETA] and replace["new"] == [REVISED_BETA]
    assert {"op": "delete", "text": "box"} in replace["words"] and {"op": "insert", "text": "crate"} in replace["words"]


def test_a_source_is_compared_with_the_last_approved_source_of_its_instrument(corpus):
    instrument = corpus.instrument()
    first = corpus.source(instrument)
    diff = corpus.get(f"/sources/{first['id']}/diff").json()
    assert diff["baseline"] is None and diff["stats"]["added"] == len(PAGE_ONE) + len(PAGE_TWO)
    corpus.approve_source(first)
    revised = corpus.source(instrument, pages=[REVISED_PAGE_ONE, PAGE_TWO])
    diff = corpus.get(f"/sources/{revised['id']}/diff").json()
    assert diff["baseline"]["id"] == first["id"]
    assert diff["stats"] == {"added": 1, "removed": 0, "changed": 1,
                             "unchanged": len(PAGE_ONE) + len(PAGE_TWO) - 1}


# --------------------------------------------------------------------------
# Validity dates
# --------------------------------------------------------------------------


def test_validity_dates_are_optional_ordered_and_not_bookkeeping(corpus):
    instrument = corpus.instrument()
    source = corpus.approve_source(corpus.source(instrument))
    provision = corpus.provision(instrument)
    r = corpus.version(source, provision, valid_from="2024-05-01", valid_to="2024-04-30")
    assert r.status_code == 422 and r.json()["code"] == "validity_not_ordered"

    one_day = corpus.version(source, provision, valid_from="2024-05-01", valid_to="2024-05-01")
    assert one_day.status_code == 201  # both ends inclusive: a single day is a range
    approved = corpus.approve_version(one_day.json())
    assert (approved["valid_from"], approved["valid_to"]) == ("2024-05-01", "2024-05-01")
    # When it applies is not when it was entered, retrieved or approved.
    assert approved["approved_at"][:10] != "2024-05-01" and approved["created_at"][:10] != "2024-05-01"
    assert corpus.get(f"/sources/{source['id']}").json()["retrieved_on"] == "2026-10-01"

    open_ended = corpus.version(source, provision, BETA).json()
    assert (open_ended["valid_from"], open_ended["valid_to"]) == (None, None)


# --------------------------------------------------------------------------
# Status history
# --------------------------------------------------------------------------


def test_status_history_grows_in_order_and_each_entry_names_its_basis(corpus):
    done = corpus.approved()
    path = f"/versions/{done.version['id']}/status-events"
    first = corpus.post(path, json={"status": "not_yet_in_force", "basis_reference": "Synthetic notice 1"})
    second = corpus.post(path, json={"status": "in_force", "effective_date": "2026-04-01",
                                     "basis_source_id": done.source["id"], "note": "Curator's own note"})
    third = corpus.post(path, json={"status": "stayed", "basis_reference": "Synthetic notice 2"})
    assert [r.status_code for r in (first, second, third)] == [201, 201, 201]
    events = corpus.get(f"/versions/{done.version['id']}").json()["status_events"]
    assert [e["status"] for e in events] == ["not_yet_in_force", "in_force", "stayed"]
    assert events[1]["basis_source"]["id"] == done.source["id"] and events[1]["effective_date"] == "2026-04-01"
    assert corpus.get(f"/versions/{done.version['id']}").json()["latest_status"] == "stayed"
    # The text the statuses describe has not moved.
    assert corpus.get(f"/versions/{done.version['id']}").json()["text"] == ALPHA


def test_a_status_needs_approved_text_and_a_basis(corpus):
    instrument = corpus.instrument()
    draft = corpus.version(corpus.source(instrument), corpus.provision(instrument)).json()
    r = corpus.post(f"/versions/{draft['id']}/status-events", json={"status": "in_force", "basis_reference": "x"})
    assert r.status_code == 409 and r.json()["code"] == "version_not_approved"
    done = corpus.approved(ALPHA, pages=[REVISED_PAGE_ONE, PAGE_TWO])  # a different file from the draft's
    r = corpus.post(f"/versions/{done.version['id']}/status-events", json={"status": "in_force"})
    assert r.status_code == 422 and r.json()["code"] == "basis_required"
    r = corpus.post(f"/versions/{done.version['id']}/status-events", json={"status": "repealed", "basis_reference": "x"})
    assert r.status_code == 422  # not in the specified vocabulary


def test_a_status_basis_must_be_an_approved_source_in_the_same_lane(corpus):
    done = corpus.approved()
    unapproved = corpus.source(corpus.instrument(title="Another synthetic fixture instrument"),
                               pages=[REVISED_PAGE_ONE])
    r = corpus.post(f"/versions/{done.version['id']}/status-events",
                    json={"status": "amended", "basis_source_id": unapproved["id"]})
    assert r.status_code == 409 and r.json()["code"] == "basis_not_approved"
    world = corpus.instrument(lane="international", title="Synthetic international fixture")
    foreign = corpus.approve_source(corpus.source(world, pages=[REVISED_PAGE_ONE, PAGE_TWO]))
    r = corpus.post(f"/versions/{done.version['id']}/status-events",
                    json={"status": "amended", "basis_source_id": foreign["id"]})
    assert r.status_code == 422 and r.json()["code"] == "lane_mismatch"


# --------------------------------------------------------------------------
# Lanes, end to end
# --------------------------------------------------------------------------


@pytest.mark.parametrize("lane", ["india", "international"])
def test_a_lane_survives_every_step(corpus, lane):
    done = corpus.approved(lane=lane)
    assert done.instrument["lane"] == done.source["lane"] == lane
    assert corpus.get(f"/instruments/{done.instrument['id']}").json()["provisions"][0]["lane"] == lane
    assert done.version["lane"] == lane
    assert corpus.get(f"/sources/{done.source['id']}").json()["lane"] == lane


def test_a_provision_never_takes_text_from_the_other_lane(corpus):
    india = corpus.source(corpus.instrument(lane="india"))
    world = corpus.instrument(lane="international", title="Synthetic international fixture")
    r = corpus.version(india, corpus.provision(world))
    assert r.status_code == 422 and r.json()["code"] == "lane_mismatch"


def test_the_lane_filter_keeps_the_lanes_apart(corpus):
    corpus.source(corpus.instrument(lane="india"))
    corpus.source(corpus.instrument(lane="international", title="Synthetic international fixture"),
                  pages=[REVISED_PAGE_ONE])
    assert {s["lane"] for s in corpus.get("/sources", params={"lane": "india"}).json()} == {"india"}
    assert {s["lane"] for s in corpus.get("/sources", params={"lane": "international"}).json()} == {"international"}
    assert {i["lane"] for i in corpus.get("/instruments", params={"lane": "international"}).json()} == {
        "international"}


# --------------------------------------------------------------------------
# Queues
# --------------------------------------------------------------------------


def test_the_queues_show_drafts_and_what_awaits_review(corpus):
    instrument = corpus.instrument()
    waiting = corpus.source(instrument)
    corpus.submit_source(waiting)
    draft_source = corpus.source(corpus.instrument(title="Second synthetic fixture instrument"),
                                 pages=[REVISED_PAGE_ONE])
    version = corpus.version(waiting, corpus.provision(instrument)).json()
    queue = corpus.get("/review-queue").json()
    assert [s["id"] for s in queue["sources"]] == [waiting["id"]] and queue["versions"] == []
    drafts = corpus.get("/drafts").json()
    assert [s["id"] for s in drafts["sources"]] == [draft_source["id"]]
    assert [v["id"] for v in drafts["versions"]] == [version["id"]]


# --------------------------------------------------------------------------
# Audit
# --------------------------------------------------------------------------


def test_every_step_is_audited_without_storing_legal_text(db, corpus):
    done = corpus.approved()
    corpus.post(f"/versions/{done.version['id']}/status-events", json={"status": "in_force", "basis_reference": "x"})
    corpus.patch(f"/versions/{done.version['id']}", json={"valid_to": "2030-01-01"})
    draft = corpus.version(done.source, done.provision, BETA).json()
    corpus.patch(f"/versions/{draft['id']}", json={"valid_to": "2030-01-01"})
    corpus.post(f"/versions/{draft['id']}/submit")
    corpus.post(f"/versions/{draft['id']}/reject", json={"reason": "Wrong span"})
    other = corpus.source(corpus.instrument(title="Second synthetic fixture instrument"), pages=[REVISED_PAGE_ONE])
    corpus.submit_source(other)
    corpus.post(f"/sources/{other['id']}/reject", json={"reason": "Wrong file"})
    failed = corpus.upload(corpus.instrument(title="Third synthetic fixture instrument"),
                           data=b"%PDF-1.4\n" + b"\x00" * 300).json()
    corpus.post(f"/sources/{failed['id']}/parse")

    actions = set(db.scalars(select(AuditEvent.action).where(AuditEvent.action.like("corpus.%"))))
    assert actions == {
        "corpus.instrument_created", "corpus.provision_created", "corpus.source_uploaded", "corpus.source_parsed",
        "corpus.source_parse_failed", "corpus.source_submitted", "corpus.source_approved", "corpus.source_rejected",
        "corpus.version_created", "corpus.version_updated", "corpus.version_submitted", "corpus.version_approved",
        "corpus.version_rejected", "corpus.status_recorded", "corpus.mutation_refused",
    }
    approval = db.scalar(select(AuditEvent).where(AuditEvent.action == "corpus.version_approved"))
    assert approval.details["text_sha256"] == sha256(ALPHA)
    assert approval.details["source_sha256"] == done.source["sha256"]
    source_approval = db.scalar(select(AuditEvent).where(AuditEvent.action == "corpus.source_approved"))
    assert source_approval.details["sha256"] == done.source["sha256"]
    assert source_approval.actor_role == "curator"
    for event in db.scalars(select(AuditEvent).where(AuditEvent.action.like("corpus.%"))):
        assert ALPHA not in str(event.details) and "fox" not in str(event.details)


def test_no_answering_or_searching_route_exists(sakti):
    paths = " ".join(sakti.app.openapi()["paths"])
    for word in ("answer", "ask", "search", "retriev", "query", "classif", "citation", "escalat", "embed"):
        assert word not in paths


def test_nothing_unapproved_is_marked_eligible(db, corpus):
    instrument = corpus.instrument()
    source = corpus.source(instrument)
    corpus.version(source, corpus.provision(instrument))
    rows = db.scalars(select(ProvisionVersion)).all()
    assert rows and all(v.review_state.value == "draft" and v.approved_at is None for v in rows)
    assert db.get(CorpusDocument, uuid.UUID(source["id"])).approved_at is None
