"""Synthetic, NON-LEGAL fixtures for the corpus tests, and a thin driver for the corpus API.

Nothing here is law, and nothing here resembles it: no section, rule, article
or statute — pangrams and placeholder sentences under a banner that says what
they are. The PDFs are generated in memory by `app.synthetic_documents` at test
time; no fixture file is committed, none is seeded, and they exist only in the
throwaway test database. They exercise the machinery and nothing else.
"""

import hashlib
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.product import Product
from app.core.security import hash_password
from app.main import create_app
from app.models import User
from app.models.enums import UserRole
from app.synthetic_documents import scanned_pdf, text_pdf
from tests.conftest import API, PASSWORD, auth

BANNER = "SYNTHETIC TEST FIXTURE - NOT A LEGAL TEXT"

PAGE_ONE = [
    BANNER,
    "Alpha paragraph. The quick brown fox jumps over the lazy dog.",
    "Beta paragraph. Pack my box with five dozen liquor jugs.",
    "Gamma paragraph. Sphinx of black quartz, judge my vow.",
]
PAGE_TWO = [
    BANNER,
    "Delta paragraph. How vexingly quick daft zebras jump.",
    "Epsilon paragraph. The five boxing wizards jump quickly.",
]
#: The same document with one word changed and one line added.
REVISED_PAGE_ONE = [
    BANNER,
    "Alpha paragraph. The quick brown fox jumps over the lazy dog.",
    "Beta paragraph. Pack my crate with five dozen liquor jugs.",
    "Gamma paragraph. Sphinx of black quartz, judge my vow.",
    "Zeta paragraph. Waltz, bad nymph, for quick jigs vex.",
]
SCANNED_PAGE = [BANNER, "Alpha paragraph", "The quick brown fox jumps"]

ALPHA = PAGE_ONE[1]
BETA = PAGE_ONE[2]
REVISED_BETA = REVISED_PAGE_ONE[2]
DELTA = PAGE_TWO[1]


def fixture_pdf(pages: list[list[str]] | None = None) -> bytes:
    return text_pdf(pages or [PAGE_ONE, PAGE_TWO])


def scanned_fixture_pdf() -> bytes:
    return scanned_pdf([SCANNED_PAGE])


def expected_text(pages: list[list[str]]) -> str:
    """What the corpus must hold for these pages: each line exactly, pages joined by a form feed."""
    return "\f".join("\n".join(lines) for lines in pages)


def sha256(data: bytes | str) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


class Corpus:
    """Drives the corpus API as one account. Every call asserts nothing unless told to."""

    def __init__(self, client: TestClient, headers: dict[str, str]):
        self.client, self.h = client, headers
        self._instruments = 0

    def get(self, path: str, **kw):
        return self.client.get(f"{API}/corpus{path}", headers=self.h, **kw)

    def post(self, path: str, **kw):
        return self.client.post(f"{API}/corpus{path}", headers=self.h, **kw)

    def patch(self, path: str, **kw):
        return self.client.patch(f"{API}/corpus{path}", headers=self.h, **kw)

    def instrument(self, lane: str = "india", title: str | None = None, **extra) -> dict:
        self._instruments += 1
        title = title or f"Synthetic fixture instrument {self._instruments}"
        body = {"lane": lane, "instrument_type": "other", "title": title, "issued_by": "The test suite", **extra}
        r = self.post("/instruments", json=body)
        assert r.status_code == 201, r.text
        return r.json()

    def upload(self, instrument: dict, *, data: bytes | None = None, name: str = "fixture.pdf",
               mime: str = "application/pdf", **form):
        fields = {
            "lane": instrument["lane"],
            "instrument_id": instrument["id"],
            "title": "Synthetic fixture source",
            "source_authority": "india_code" if instrument["lane"] == "india" else "wipo_lex",
            "document_type": "other",
            "retrieved_on": "2026-10-01",
            "source_reference": "Synthetic test fixture; not an official document",
            **form,
        }
        fields = {k: v for k, v in fields.items() if v is not None}
        return self.post("/sources", data=fields, files={"file": (name, data if data is not None else fixture_pdf(), mime)})

    def source(self, instrument: dict | None = None, *, pages: list[list[str]] | None = None, parse: bool = True,
               data: bytes | None = None) -> dict:
        instrument = instrument or self.instrument()
        r = self.upload(instrument, data=data if data is not None else fixture_pdf(pages))
        assert r.status_code == 201, r.text
        source = r.json()
        if parse:
            r = self.post(f"/sources/{source['id']}/parse")
            assert r.status_code == 200, r.text
            source = r.json()
        return source

    def text(self, source: dict) -> dict:
        r = self.get(f"/sources/{source['id']}/text")
        assert r.status_code == 200, r.text
        return r.json()

    def span(self, source: dict, needle: str) -> tuple[int, int]:
        """Document offsets of `needle` in a source's text."""
        body = self.text(source)
        document = "\f".join(page["text"] for page in body["pages"])
        start = document.index(needle)
        return start, start + len(needle)

    def provision(self, instrument: dict, locator: str = "Alpha", locator_type: str = "paragraph") -> dict:
        r = self.post(f"/instruments/{instrument['id']}/provisions",
                      json={"locator": locator, "locator_type": locator_type})
        assert r.status_code == 201, r.text
        return r.json()

    def version(self, source: dict, provision: dict, needle: str = ALPHA, **extra):
        start, end = self.span(source, needle)
        return self.post(f"/sources/{source['id']}/versions",
                         json={"provision_id": provision["id"], "char_start": start, "char_end": end, **extra})

    def submit_source(self, source: dict) -> dict:
        r = self.post(f"/sources/{source['id']}/submit")
        assert r.status_code == 200, r.text
        return r.json()

    def approve_source(self, source: dict, **extra) -> dict:
        self.submit_source(source)
        r = self.post(f"/sources/{source['id']}/approve", json={"expected_sha256": source["sha256"], **extra})
        assert r.status_code == 200, r.text
        return r.json()

    def approve_version(self, version: dict, **extra) -> dict:
        r = self.post(f"/versions/{version['id']}/submit")
        assert r.status_code == 200, r.text
        r = self.post(f"/versions/{version['id']}/approve",
                      json={"expected_text_sha256": version["text_sha256"], **extra})
        assert r.status_code == 200, r.text
        return r.json()

    def approved(self, needle: str = ALPHA, *, pages: list[list[str]] | None = None, lane: str = "india"):
        """An approved source and an approved version cut from it."""
        instrument = self.instrument(lane=lane)
        source = self.approve_source(self.source(instrument, pages=pages))
        provision = self.provision(instrument)
        r = self.version(source, provision, needle)
        assert r.status_code == 201, r.text
        version = self.approve_version(r.json())
        return SimpleNamespace(instrument=instrument, source=source, provision=provision, version=version)


@pytest.fixture
def sakti():
    with TestClient(create_app(Product.IP_SAKTI)) as c:
        yield c


@pytest.fixture
def sakti_account(sakti, db):
    def _make(role: UserRole, email: str | None = None) -> SimpleNamespace:
        email = email or f"{role.value}@sakti.example.com"
        user = User(role=role, email=email, password_hash=hash_password(PASSWORD))
        db.add(user)
        db.commit()
        token = sakti.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]
        return SimpleNamespace(h=auth(token), user_id=str(user.id), email=email)

    return _make


@pytest.fixture
def curator(sakti_account):
    return sakti_account(UserRole.CURATOR)


@pytest.fixture
def corpus(sakti, curator) -> Corpus:
    return Corpus(sakti, curator.h)
