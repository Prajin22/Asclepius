"""The corpus data model holds its own invariants (D-081–D-085).

These tests go around the service and the API on purpose: they write to the
database directly and expect it to refuse. Lane separation, approved-text
immutability and the append-only status history are properties of the schema,
not of code that could be forgotten. Pure text functions (document assembly,
chunking, diff) are tested here too.
"""

import uuid
from datetime import date

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.models import (
    CorpusChunk,
    CorpusDocument,
    CorpusPage,
    Instrument,
    Provision,
    ProvisionStatusEvent,
    ProvisionVersion,
)
from app.models.enums import (
    CorpusDocumentType,
    CorpusLane,
    CorpusReviewState,
    InstrumentType,
    LocatorType,
    ProvisionStatus,
    SourceAuthority,
    TermsStatus,
)
from app.sakti.corpus import diff, text
from app.sakti.corpus.authorities import AUTHORITIES
from tests.corpus_fixtures import (  # noqa: F401  (fixtures)
    ALPHA,
    BETA,
    REVISED_BETA,
    corpus,
    curator,
    sakti,
    sakti_account,
)

CORPUS_MODELS = (Instrument, CorpusDocument, CorpusChunk, Provision, ProvisionVersion, ProvisionStatusEvent)


def _refused(db, statement: str, **params) -> None:
    with pytest.raises(IntegrityError):
        db.execute(sa.text(statement), params)
        db.commit()
    db.rollback()


# --------------------------------------------------------------------------
# Lanes
# --------------------------------------------------------------------------


@pytest.mark.parametrize("model", CORPUS_MODELS, ids=lambda m: m.__tablename__)
def test_every_corpus_record_has_exactly_one_lane(model):
    column = model.__table__.c.lane
    assert column.nullable is False
    checks = [c for c in model.__table__.constraints if isinstance(c, sa.CheckConstraint) and "lane" in str(c.sqltext)]
    assert checks, "the lane is constrained to india | international"
    assert {lane.value for lane in CorpusLane} == {"india", "international"}


def test_a_provision_cannot_join_an_instrument_of_the_other_lane(db, corpus, curator):
    instrument = corpus.instrument(lane="india")
    db.add(Provision(instrument_id=uuid.UUID(instrument["id"]), lane=CorpusLane.INTERNATIONAL, locator="x",
                     locator_type=LocatorType.OTHER, created_by_user_id=uuid.UUID(curator.user_id)))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_a_version_cannot_take_text_from_a_source_in_the_other_lane(db, corpus, curator):
    india = corpus.source(corpus.instrument(lane="india"))
    world = corpus.instrument(lane="international", title="Synthetic international fixture")
    provision = corpus.provision(world)
    db.add(ProvisionVersion(
        provision_id=uuid.UUID(provision["id"]), lane=CorpusLane.INTERNATIONAL, document_id=uuid.UUID(india["id"]),
        version_number=1, text="x", text_sha256="0" * 64, char_start=0, char_end=1, page_start=1, page_end=1,
        created_by_user_id=uuid.UUID(curator.user_id),
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_chunks_carry_their_documents_lane(db, corpus):
    source = corpus.source(corpus.instrument(lane="international", title="Synthetic international fixture"))
    lanes = set(db.scalars(sa.select(CorpusChunk.lane).where(CorpusChunk.document_id == uuid.UUID(source["id"]))))
    assert lanes == {CorpusLane.INTERNATIONAL}


@pytest.mark.parametrize("table", ["instruments", "corpus_documents", "provisions", "provision_versions"])
def test_no_record_ever_changes_lane(db, corpus, table):
    instrument = corpus.instrument()
    source = corpus.source(instrument)
    provision = corpus.provision(instrument)
    version = corpus.version(source, provision).json()
    ids = {"instruments": instrument["id"], "corpus_documents": source["id"], "provisions": provision["id"],
           "provision_versions": version["id"]}
    _refused(db, f"UPDATE {table} SET lane = 'international' WHERE id = :id", id=_id(db, ids[table]))


# --------------------------------------------------------------------------
# Immutability (D-084)
# --------------------------------------------------------------------------


def _id(db, value: str):
    return uuid.UUID(value).hex if db.bind.dialect.name == "sqlite" else value


def test_approved_text_cannot_be_changed_even_directly_in_the_database(db, corpus):
    done = corpus.approved()
    _refused(db, "UPDATE provision_versions SET text = 'something else' WHERE id = :id", id=_id(db, done.version["id"]))
    _refused(db, "UPDATE provision_versions SET valid_to = '2030-01-01' WHERE id = :id", id=_id(db, done.version["id"]))
    _refused(db, "UPDATE corpus_documents SET title = 'renamed' WHERE id = :id", id=_id(db, done.source["id"]))
    stored = db.get(ProvisionVersion, uuid.UUID(done.version["id"]))
    assert stored.text == ALPHA


def test_rejected_records_are_final_too(db, corpus):
    source = corpus.source()
    corpus.submit_source(source)
    assert corpus.post(f"/sources/{source['id']}/reject", json={"reason": "Test"}).status_code == 200
    _refused(db, "UPDATE corpus_documents SET review_state = 'approved' WHERE id = :id", id=_id(db, source["id"]))


@pytest.mark.parametrize("table", ["corpus_pages", "corpus_chunks"])
def test_read_text_is_never_rewritten(db, corpus, table):
    source = corpus.source()
    _refused(db, f"UPDATE {table} SET text = 'replaced' WHERE document_id = :id", id=_id(db, source["id"]))


def test_status_history_is_append_only(db, corpus):
    done = corpus.approved()
    r = corpus.post(f"/versions/{done.version['id']}/status-events",
                    json={"status": "in_force", "basis_reference": "Synthetic reference"})
    assert r.status_code == 201
    _refused(db, "UPDATE provision_status_events SET status = 'stayed' WHERE id = :id", id=_id(db, r.json()["id"]))


def test_a_draft_can_still_be_corrected(db, corpus):
    instrument = corpus.instrument()
    version = corpus.version(corpus.source(instrument), corpus.provision(instrument)).json()
    db.execute(sa.text("UPDATE provision_versions SET valid_to = '2030-01-01' WHERE id = :id"),
               {"id": _id(db, version["id"])})
    db.commit()
    assert db.get(ProvisionVersion, uuid.UUID(version["id"])).valid_to == date(2030, 1, 1)


# --------------------------------------------------------------------------
# Constraints
# --------------------------------------------------------------------------


def test_validity_cannot_end_before_it_starts_in_the_database(db, corpus):
    instrument = corpus.instrument()
    version = corpus.version(corpus.source(instrument), corpus.provision(instrument)).json()
    _refused(db, "UPDATE provision_versions SET valid_from = '2025-01-02', valid_to = '2025-01-01' WHERE id = :id",
             id=_id(db, version["id"]))


def test_an_approval_must_say_who_and_when(db, corpus):
    instrument = corpus.instrument()
    version = corpus.version(corpus.source(instrument), corpus.provision(instrument)).json()
    _refused(db, "UPDATE provision_versions SET review_state = 'approved' WHERE id = :id", id=_id(db, version["id"]))


def test_a_source_must_say_where_it_came_from(db, corpus):
    source = corpus.source()
    _refused(db, "UPDATE corpus_documents SET source_url = NULL, source_reference = NULL WHERE id = :id",
             id=_id(db, source["id"]))


def test_an_unread_source_cannot_enter_review(db, corpus):
    source = corpus.source(parse=False)
    _refused(db, "UPDATE corpus_documents SET review_state = 'under_review' WHERE id = :id", id=_id(db, source["id"]))


def test_version_numbers_are_unique_per_provision(db, corpus):
    instrument = corpus.instrument()
    source = corpus.source(instrument)
    provision = corpus.provision(instrument)
    first = corpus.version(source, provision).json()
    second = corpus.version(source, provision, BETA).json()
    assert (first["version_number"], second["version_number"]) == (1, 2)
    _refused(db, "UPDATE provision_versions SET version_number = 1 WHERE id = :id", id=_id(db, second["id"]))


def test_the_same_file_cannot_be_live_twice(db, corpus):
    instrument = corpus.instrument()
    corpus.source(instrument, parse=False)
    r = corpus.upload(instrument)
    assert r.status_code == 409 and r.json()["code"] == "duplicate_source"


def test_a_status_must_name_its_basis(db, corpus, curator):
    done = corpus.approved()
    db.add(ProvisionStatusEvent(
        provision_version_id=uuid.UUID(done.version["id"]), lane=CorpusLane.INDIA, status=ProvisionStatus.IN_FORCE,
        recorded_by_user_id=uuid.UUID(curator.user_id),
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# --------------------------------------------------------------------------
# Vocabularies and authorities
# --------------------------------------------------------------------------


def test_the_status_vocabulary_is_exactly_the_specified_one():
    # The build brief's "in force, stayed or omitted" and the Phase 2 brief's list (D-085).
    assert {s.value for s in ProvisionStatus} == {
        "in_force", "not_yet_in_force", "amended", "superseded", "stayed", "omitted", "disputed", "withdrawn",
    }


def test_the_review_states_are_exactly_draft_review_approved_rejected():
    assert [s.value for s in CorpusReviewState] == ["draft", "under_review", "approved", "rejected"]


def test_every_authority_is_official_belongs_to_one_lane_and_has_unverified_terms():
    assert set(AUTHORITIES) == set(SourceAuthority)
    assert {a.lane for a in AUTHORITIES.values()} == {CorpusLane.INDIA, CorpusLane.INTERNATIONAL}
    assert all(a.terms_status == TermsStatus.UNKNOWN for a in AUTHORITIES.values())
    assert AUTHORITIES[SourceAuthority.WIPO_LEX].lane == CorpusLane.INTERNATIONAL
    assert {a.lane for code, a in AUTHORITIES.items() if code != SourceAuthority.WIPO_LEX} == {CorpusLane.INDIA}


def test_instrument_and_document_types_carry_no_legal_conclusion():
    words = " ".join([*InstrumentType, *CorpusDocumentType, *LocatorType])
    for conclusion in ("valid", "applicable", "binding", "compliant", "legal", "advice", "required"):
        assert conclusion not in words


def test_validity_and_bookkeeping_dates_are_separate_columns():
    columns = set(ProvisionVersion.__table__.c.keys())
    assert {"valid_from", "valid_to", "approved_at", "created_at"} <= columns
    assert {"retrieved_on", "source_date", "approved_at", "created_at"} <= set(CorpusDocument.__table__.c.keys())


# --------------------------------------------------------------------------
# Pure text functions
# --------------------------------------------------------------------------


def test_the_document_text_is_the_pages_joined_by_a_form_feed():
    document, starts = text.assemble(["one\ntwo", "", "three"])
    assert document == "one\ntwo\f\fthree"
    assert starts == [0, 8, 9]
    assert [document[s:s + len(p)] for s, p in zip(starts, ["one\ntwo", "", "three"], strict=True)] == [
        "one\ntwo", "", "three"]


def test_chunks_are_exact_line_bounded_slices_that_never_cross_a_page():
    pages = ["a" * 50 + "\n" + "b" * 50 + "\n" + "c" * 50, "d" * 10 + "\n\n" + "e" * 10]
    document, starts = text.assemble(pages)
    chunks = text.chunk_pages([(i + 1, s, p) for i, (s, p) in enumerate(zip(starts, pages, strict=True))],
                              max_chars=110)
    assert [c.page_number for c in chunks] == [1, 1, 2]
    assert [document[c.char_start:c.char_end] for c in chunks] == [
        "a" * 50 + "\n" + "b" * 50, "c" * 50, "d" * 10 + "\n\n" + "e" * 10]
    assert [c.ordinal for c in chunks] == [0, 1, 2]


def test_a_line_longer_than_the_limit_is_a_chunk_of_its_own_and_is_never_cut():
    pages = ["x" * 30 + "\n" + "y" * 500 + "\n" + "z" * 30]
    chunks = text.chunk_pages([(1, 0, pages[0])], max_chars=100)
    assert [pages[0][c.char_start:c.char_end] for c in chunks] == ["x" * 30, "y" * 500, "z" * 30]


def test_chunking_is_deterministic_and_skips_blank_pages():
    pages = [(1, 0, "alpha\nbeta"), (2, 11, ""), (3, 12, "gamma")]
    assert text.chunk_pages(pages) == text.chunk_pages(pages)
    assert [c.page_number for c in text.chunk_pages(pages)] == [1, 3]


def test_a_span_knows_its_pages():
    starts, lengths = [0, 8, 9], [7, 0, 5]
    assert text.pages_of_span(starts, lengths, 0, 3) == (1, 1)
    assert text.pages_of_span(starts, lengths, 4, 12) == (1, 3)
    assert text.pages_of_span(starts, lengths, 9, 14) == (3, 3)


def test_the_diff_is_deterministic_and_says_nothing_of_its_own():
    old = "\n".join(["keep one", "keep two", "keep three", "keep four", BETA, "keep five"])
    new = "\n".join(["keep one", "keep two", "keep three", "keep four", REVISED_BETA, "keep five", "added"])
    first, second = diff.diff_texts(old, new), diff.diff_texts(old, new)
    assert first == second
    assert first["stats"] == {"added": 1, "removed": 0, "changed": 1, "unchanged": 5}
    replace = next(b for b in first["blocks"] if b["op"] == "replace")
    assert replace["old"] == [BETA] and replace["new"] == [REVISED_BETA]
    assert {"op": "delete", "text": "box"} in replace["words"]
    assert {"op": "insert", "text": "crate"} in replace["words"]
    # Every character of the diff comes from one of the two texts.
    for block in first["blocks"]:
        for line in [*block.get("lines", []), *block.get("tail", []), *block.get("new", [])]:
            assert line in new.splitlines()


def test_the_diff_folds_long_unchanged_runs_and_says_how_many_lines_it_folded():
    old = "\n".join(f"line {i}" for i in range(20))
    new = old.replace("line 10", "line ten")
    blocks = diff.diff_texts(old, new)["blocks"]
    assert blocks[0]["op"] == "equal" and blocks[0]["lines"] == [] and blocks[0]["skipped"] == 7
    assert blocks[0]["tail"] == ["line 7", "line 8", "line 9"]
    assert diff.diff_texts(old, old) == {"stats": {"added": 0, "removed": 0, "changed": 0, "unchanged": 20},
                                         "blocks": [{"op": "equal", "old_start": 1, "new_start": 1, "lines": [],
                                                     "skipped": 20, "tail": []}]}


def test_text_hashes_are_sha256_of_utf8():
    assert text.sha256_text("க") == __import__("hashlib").sha256("க".encode()).hexdigest()


def test_model_timestamps_are_timezone_aware():
    for model in (CorpusDocument, CorpusPage, ProvisionVersion, ProvisionStatusEvent):
        for column in model.__table__.c:
            if isinstance(column.type, sa.DateTime):
                assert column.type.timezone, f"{model.__tablename__}.{column.name}"
