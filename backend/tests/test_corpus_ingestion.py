"""Bringing an official source in: upload, provenance, reading, integrity (Phase 2).

The fixtures are synthetic and non-legal (`tests/corpus_fixtures.py`). What is
tested is the machinery: a file is accepted only if it is what it claims to be,
it is kept byte for byte, its text is copied exactly or marked as machine
transcription, nothing is half-read, and nothing calls an AI provider or the
network.
"""

import hashlib
import urllib.request
import uuid

import httpx
import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.models import AIArtifact, CorpusChunk, CorpusDocument, CorpusPage
from app.providers.documents.ocr import ocr_available
from app.providers.storage import get_storage
from tests.conftest import EXE_BYTES, PNG_BYTES
from tests.corpus_fixtures import (  # noqa: F401  (fixtures)
    BANNER,
    PAGE_ONE,
    PAGE_TWO,
    corpus,
    curator,
    expected_text,
    fixture_pdf,
    sakti,
    sakti_account,
    scanned_fixture_pdf,
    sha256,
)

# --------------------------------------------------------------------------
# Upload
# --------------------------------------------------------------------------


def test_a_valid_source_is_stored_as_a_draft_with_its_provenance(corpus):
    instrument = corpus.instrument()
    data = fixture_pdf()
    r = corpus.upload(instrument, data=data, source_url="https://example.org/fixture.pdf", source_date="2026-09-01")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["review_state"] == "draft" and body["ingestion_state"] == "uploaded"
    assert body["sha256"] == hashlib.sha256(data).hexdigest()
    assert body["size_bytes"] == len(data) and body["mime_type"] == "application/pdf"
    assert body["lane"] == "india" and body["instrument"]["id"] == instrument["id"]
    assert body["source_authority"] == "india_code" and body["authority_name"] == "India Code"
    assert body["source_url"] == "https://example.org/fixture.pdf"
    assert body["source_reference"].startswith("Synthetic")
    assert (body["source_date"], body["retrieved_on"]) == ("2026-09-01", "2026-10-01")
    assert body["terms_status"] == "unknown"
    assert body["page_count"] is None and body["text_sha256"] is None  # not read yet


def test_the_storage_location_never_leaves_the_api(corpus):
    source = corpus.source()
    for path in (f"/sources/{source['id']}", "/sources", f"/sources/{source['id']}/text", "/drafts"):
        assert "storage" not in corpus.get(path).text
        assert "corpus/sources/" not in corpus.get(path).text


def test_the_original_is_returned_byte_for_byte_and_never_rendered_here(corpus):
    data = fixture_pdf()
    source = corpus.source(data=data)
    r = corpus.get(f"/sources/{source['id']}/original")
    assert r.status_code == 200 and r.content == data
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in r.headers["content-security-policy"]


@pytest.mark.parametrize("content,mime,name,code", [
    (b"", "application/pdf", "empty.pdf", "empty_file"),
    (PNG_BYTES, "image/png", "scan.png", "unsupported_type"),
    (EXE_BYTES, "application/x-msdownload", "tool.exe", "unsupported_type"),
    (EXE_BYTES, "application/pdf", "tool.pdf", "content_mismatch"),
    (b"just some text, not a pdf", "application/pdf", "notes.pdf", "content_mismatch"),
    (None, "application/pdf", "fixture.exe", "bad_extension"),
])
def test_anything_that_is_not_a_pdf_is_refused_and_nothing_is_kept(db, corpus, content, mime, name, code):
    instrument = corpus.instrument()
    r = corpus.upload(instrument, data=fixture_pdf() if content is None else content, name=name, mime=mime)
    assert r.status_code == 422 and r.json()["code"] == code
    assert db.scalar(select(func.count()).select_from(CorpusDocument)) == 0


def test_an_oversized_file_is_refused(corpus, monkeypatch):
    monkeypatch.setattr(get_settings(), "corpus_max_upload_bytes", 500)
    r = corpus.upload(corpus.instrument())
    assert r.status_code == 422 and r.json()["code"] == "file_too_large"


def test_a_file_name_is_never_a_path(corpus):
    r = corpus.upload(corpus.instrument(), name="../../etc/passwd.pdf")
    assert r.status_code == 201
    assert r.json()["file_name"] == "passwd.pdf"


@pytest.mark.parametrize("url", [
    "ftp://example.org/x.pdf", "javascript:alert(1)", "file:///etc/passwd", "https://user:pw@example.org/x",
    "https://exa mple.org/x", "not a url", "http://example.org:99999/x",
])
def test_a_source_url_must_be_plain_http_or_https(corpus, url):
    r = corpus.upload(corpus.instrument(), source_url=url)
    assert r.status_code == 422 and r.json()["code"] == "invalid_source_url"


def test_a_source_must_say_where_it_came_from(corpus):
    r = corpus.upload(corpus.instrument(), source_reference=None)
    assert r.status_code == 422 and r.json()["code"] == "provenance_required"


def test_only_a_listed_official_authority_is_accepted(corpus):
    r = corpus.upload(corpus.instrument(), source_authority="wikipedia")
    assert r.status_code == 422
    authorities = corpus.get("/authorities").json()
    assert {a["code"] for a in authorities} == {"india_code", "e_gazette", "ip_india", "nba", "fssai", "wipo_lex"}
    assert {a["terms_status"] for a in authorities} == {"unknown"}


def test_an_authority_publishes_for_one_lane_only(corpus):
    r = corpus.upload(corpus.instrument(lane="india"), source_authority="wipo_lex")
    assert r.status_code == 422 and r.json()["code"] == "authority_not_in_lane"
    world = corpus.instrument(lane="international", title="Synthetic international fixture")
    r = corpus.upload(world, source_authority="india_code")
    assert r.status_code == 422 and r.json()["code"] == "authority_not_in_lane"


def test_a_source_never_lands_in_a_lane_other_than_its_instruments(corpus):
    r = corpus.upload(corpus.instrument(lane="india"), lane="international", source_authority="wipo_lex")
    assert r.status_code == 422 and r.json()["code"] == "lane_mismatch"


def test_a_retrieval_date_in_the_future_is_refused(corpus):
    r = corpus.upload(corpus.instrument(), retrieved_on="2099-01-01")
    assert r.status_code == 422 and r.json()["code"] == "date_in_future"


def test_a_rejected_file_may_be_uploaded_again(corpus):
    instrument = corpus.instrument()
    first = corpus.source(instrument)
    corpus.submit_source(first)
    assert corpus.post(f"/sources/{first['id']}/reject", json={"reason": "Wrong file"}).status_code == 200
    assert corpus.upload(instrument).status_code == 201


def test_a_url_is_recorded_and_never_fetched(corpus, monkeypatch):
    def no_network(*_, **__):
        raise AssertionError("the server tried to fetch a URL")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    # Real transports only: the test client talks to the app in-process through its own.
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", no_network)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", no_network)
    r = corpus.upload(corpus.instrument(), source_url="https://example.org/fixture.pdf")
    assert r.status_code == 201
    assert corpus.post(f"/sources/{r.json()['id']}/parse").status_code == 200


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------


def test_a_text_layer_is_copied_exactly(db, corpus):
    source = corpus.source(pages=[PAGE_ONE, PAGE_TWO])
    assert source["ingestion_state"] == "parsed" and source["ingestion_issues"] == []
    assert source["page_count"] == 2 and source["extraction_methods"] == ["pdf_text_layer"]

    body = corpus.text(source)
    assert [p["text"] for p in body["pages"]] == ["\n".join(PAGE_ONE), "\n".join(PAGE_TWO)]
    document = expected_text([PAGE_ONE, PAGE_TWO])
    assert body["text_sha256"] == source["text_sha256"] == sha256(document)
    assert body["text_length"] == source["text_length"] == len(document)
    assert [p["char_start"] for p in body["pages"]] == [0, len("\n".join(PAGE_ONE)) + 1]
    assert all(p["confidence"] is None for p in body["pages"])  # exact, not estimated


def test_chunks_are_exact_slices_of_the_document_text(db, corpus):
    source = corpus.source()
    document = expected_text([PAGE_ONE, PAGE_TWO])
    chunks = db.scalars(select(CorpusChunk).where(CorpusChunk.document_id == uuid.UUID(source["id"]))
                        .order_by(CorpusChunk.ordinal)).all()
    assert chunks, "a read source has chunks"
    for chunk in chunks:
        assert chunk.text == document[chunk.char_start:chunk.char_end]
        assert chunk.text_sha256 == sha256(chunk.text)
        assert "\f" not in chunk.text  # never across a page
    assert {c.page_number for c in chunks} == {1, 2}
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_reading_the_same_file_twice_gives_the_same_text(corpus):
    first = corpus.source(corpus.instrument())
    other = corpus.instrument(title="Second synthetic fixture instrument")
    corpus.submit_source(first)
    corpus.post(f"/sources/{first['id']}/reject", json={"reason": "Re-read the same file"})
    second = corpus.source(other)
    assert first["text_sha256"] == second["text_sha256"]
    assert corpus.text(first)["chunks"] == corpus.text(second)["chunks"]


def test_a_source_is_read_once(corpus):
    source = corpus.source()
    r = corpus.post(f"/sources/{source['id']}/parse")
    assert r.status_code == 409 and r.json()["code"] == "already_parsed"


def test_an_unreadable_file_fails_whole_and_cannot_be_reviewed(db, corpus):
    instrument = corpus.instrument()
    broken = b"%PDF-1.4\n" + b"\x00garbage" * 100 + b"\n%%EOF\n"
    source = corpus.upload(instrument, data=broken).json()
    r = corpus.post(f"/sources/{source['id']}/parse")
    assert r.status_code == 200
    assert r.json()["ingestion_state"] == "failed" and r.json()["parse_error_code"]
    assert db.scalar(select(func.count()).select_from(CorpusPage)) == 0
    r = corpus.post(f"/sources/{source['id']}/submit")
    assert r.status_code == 409 and r.json()["code"] == "source_not_read"
    assert corpus.post(f"/sources/{source['id']}/parse").status_code == 200  # may be retried


def test_a_source_longer_than_the_limit_is_refused_rather_than_read_in_part(db, corpus, monkeypatch):
    monkeypatch.setattr(get_settings(), "corpus_max_pages", 1)
    source = corpus.source(pages=[PAGE_ONE, PAGE_TWO])
    assert source["ingestion_state"] == "failed" and source["parse_error_code"] == "too_many_pages"
    assert source["page_count"] == 2
    assert db.scalar(select(func.count()).select_from(CorpusPage)) == 0


def test_a_text_without_a_text_layer_or_ocr_needs_review_and_is_not_guessed(db, corpus, monkeypatch):
    monkeypatch.setattr(get_settings(), "ocr_engine", "none")
    source = corpus.source(data=scanned_fixture_pdf())
    assert source["ingestion_state"] == "failed" and source["parse_error_code"] == "no_text_found"


@pytest.mark.skipif(not ocr_available(), reason="offline OCR engine not installed")
def test_a_scanned_page_is_read_by_local_ocr_and_marked_for_review(corpus):
    source = corpus.source(data=scanned_fixture_pdf())
    assert source["ingestion_state"] == "needs_review"
    assert "ocr_text_requires_verification" in source["ingestion_issues"]
    assert source["extraction_methods"] == ["ocr"]
    page = corpus.text(source)["pages"][0]
    assert page["method"] == "ocr" and page["confidence"] is not None
    assert "rapidocr" in page["engine"]

    corpus.submit_source(source)
    r = corpus.post(f"/sources/{source['id']}/approve", json={"expected_sha256": source["sha256"]})
    assert r.status_code == 422 and r.json()["code"] == "issues_not_acknowledged"
    r = corpus.post(f"/sources/{source['id']}/approve",
                    json={"expected_sha256": source["sha256"], "acknowledge_issues": True})
    assert r.status_code == 200 and r.json()["issues_acknowledged"] is True


def test_reading_calls_no_ai_provider(db, corpus, monkeypatch):
    import app.providers.ai as ai

    def forbidden(*_, **__):
        raise AssertionError("the corpus called an AI provider")

    monkeypatch.setattr(ai, "get_ai_provider", forbidden)
    monkeypatch.setattr(ai, "build_ai_provider", forbidden)
    source = corpus.source()
    assert source["ingestion_state"] == "parsed"
    assert db.scalar(select(func.count()).select_from(AIArtifact)) == 0


# --------------------------------------------------------------------------
# Integrity
# --------------------------------------------------------------------------


def _tamper(db, source: dict) -> None:
    reference = db.get(CorpusDocument, uuid.UUID(source["id"])).storage_reference
    storage = get_storage()
    storage.delete(reference)
    storage.put(reference.removeprefix("local:"), fixture_pdf([[BANNER, "Something else entirely."]]),
                "application/pdf")


def test_a_changed_file_is_never_served_or_read(db, corpus):
    source = corpus.source(parse=False)
    _tamper(db, source)
    assert corpus.get(f"/sources/{source['id']}/original").json()["code"] == "document_integrity_failed"
    r = corpus.post(f"/sources/{source['id']}/parse")
    assert r.status_code == 409 and r.json()["code"] == "document_integrity_failed"


def test_a_changed_file_cannot_be_approved(db, corpus):
    source = corpus.source()
    corpus.submit_source(source)
    _tamper(db, source)
    r = corpus.post(f"/sources/{source['id']}/approve", json={"expected_sha256": source["sha256"]})
    assert r.status_code == 409 and r.json()["code"] == "document_integrity_failed"
    assert corpus.get(f"/sources/{source['id']}").json()["review_state"] == "under_review"
