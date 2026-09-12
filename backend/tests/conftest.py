"""Test configuration.

Default: a throwaway SQLite file (fast, no services needed).
Set TEST_DATABASE_URL to run against PostgreSQL, e.g.
  postgresql+psycopg://carebridge:carebridge_dev_password@localhost:5432/carebridge_test
The database name must contain "test" — tables are dropped.
"""

import os
import pathlib
import tempfile
from types import SimpleNamespace

_TMP = pathlib.Path(tempfile.mkdtemp(prefix="carebridge-test-"))
_TEST_DB = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{(_TMP / 'test.db').as_posix()}"
if "test" not in _TEST_DB.rsplit("/", 1)[-1]:
    raise RuntimeError("Refusing to run tests: TEST_DATABASE_URL database name must contain 'test'")

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = _TEST_DB
os.environ["STORAGE_LOCAL_ROOT"] = str(_TMP / "storage")
os.environ["JWT_SECRET"] = "test-secret-" + "x" * 40
os.environ["AI_PROVIDER"] = "mock"
os.environ["MAX_UPLOAD_BYTES"] = str(1024 * 1024)

# A developer's .env (with real keys, DEMO_MODE=false, custom limits) must never
# make the test suite call a live provider or change behaviour under test.
# Process environment variables take precedence over the .env file.
os.environ["DEMO_MODE"] = "true"
os.environ["AI_MODEL"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["AI_CACHE_ENABLED"] = "true"
os.environ["AI_RATE_LIMIT_PER_HOUR"] = "20"
os.environ["AI_RATE_LIMIT_PER_DAY"] = "100"
os.environ["AI_DAILY_COST_LIMIT_USD"] = "1.0"
os.environ["CORS_ORIGINS"] = "http://localhost:3000,http://localhost:3001"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.schemas.doctor import DoctorCreate  # noqa: E402
from app.services import auth_service  # noqa: E402

PASSWORD = "Passw0rd!"
PDF_BYTES = b"%PDF-1.4\n% synthetic test document\n" + b"0" * 200 + b"\n%%EOF\n"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
EXE_BYTES = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 64

API = "/api/v1"


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def client():
    with TestClient(fastapi_app) as c:
        yield c


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_patient(client):
    def _make(email: str = "arun@example.com", name: str = "Arun Kumar", lang: str = "ta") -> SimpleNamespace:
        r = client.post(
            f"{API}/auth/register",
            json={"email": email, "password": PASSWORD, "display_name": name, "preferred_language": lang},
        )
        assert r.status_code == 201, r.text
        token = r.json()["access_token"]
        me = client.get(f"{API}/auth/me", headers=auth(token)).json()
        return SimpleNamespace(token=token, id=me["profile_id"], user_id=me["user"]["id"], h=auth(token))

    return _make


@pytest.fixture
def make_doctor(client, db):
    def _make(
        email: str = "meera@example.com",
        name: str = "Dr. Meera Sharma",
        specialization: str = "General Medicine",
        languages: tuple[str, ...] = ("en", "ta"),
    ) -> SimpleNamespace:
        auth_service.create_doctor(
            db,
            DoctorCreate(
                email=email,
                password=PASSWORD,
                name=name,
                specialization=specialization,
                qualification="MBBS",
                registration_identifier=f"TEST-{email}",
                languages=list(languages),
            ),
            actor=None,
        )
        r = client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        me = client.get(f"{API}/auth/me", headers=auth(token)).json()
        return SimpleNamespace(token=token, id=me["profile_id"], user_id=me["user"]["id"], h=auth(token))

    return _make


@pytest.fixture
def make_admin(client, db):
    def _make(email: str = "admin@example.com") -> SimpleNamespace:
        from app.core.security import hash_password
        from app.models import User
        from app.models.enums import UserRole

        db.add(User(role=UserRole.ADMIN, email=email, password_hash=hash_password(PASSWORD)))
        db.commit()
        token = client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]
        return SimpleNamespace(token=token, h=auth(token))

    return _make


def upload(client, patient, content: bytes = PDF_BYTES, name: str = "report.pdf", mime: str = "application/pdf",
           document_type: str = "lab_report"):
    return client.post(
        f"{API}/patients/me/documents",
        files={"file": (name, content, mime)},
        data={"document_type": document_type},
        headers=patient.h,
    )


@pytest.fixture
def seeded_case(client, make_patient, make_doctor):
    """Patient with a problem, history, two documents, and a doctor to consult."""
    patient = make_patient()
    doctor = make_doctor()
    problem = client.post(
        f"{API}/patients/me/current-problems",
        json={"text": "மூன்று நாட்களாக தலைவலி மற்றும் தலைச்சுற்றல்", "language": "ta"},
        headers=patient.h,
    ).json()
    shared_rec = client.post(
        f"{API}/patients/me/records",
        json={"type": "condition", "title": "Hypertension", "content": "5 years", "source_language": "en"},
        headers=patient.h,
    ).json()
    private_rec = client.post(
        f"{API}/patients/me/records",
        json={"type": "history_note", "title": "Private note", "content": "not shared", "source_language": "en"},
        headers=patient.h,
    ).json()
    shared_doc = upload(client, patient, name="lipid.pdf").json()
    private_doc = upload(client, patient, name="private.pdf").json()
    return SimpleNamespace(
        patient=patient, doctor=doctor, problem=problem, shared_rec=shared_rec, private_rec=private_rec,
        shared_doc=shared_doc, private_doc=private_doc,
    )


def request_consultation(client, case, doctor=None, **share_overrides):
    doctor = doctor or case.doctor
    share = {
        "current_problem_ids": [case.problem["id"]],
        "medical_record_ids": [case.shared_rec["id"]],
        "document_ids": [case.shared_doc["id"]],
        "consultation_ids": [],
        "prescription_ids": [],
    }
    share.update(share_overrides)
    return client.post(
        f"{API}/patients/me/consultations",
        json={"doctor_id": doctor.id, "share": share, "request_message": "Please review", "request_language": "en"},
        headers=case.patient.h,
    )


RX = {
    "items": [
        {"medication": "Paracetamol 500 mg", "dosage": "1 tablet", "frequency": "Twice daily",
         "duration": "3 days", "instructions": "After food"}
    ],
    "instructions": "Rest and drink fluids.",
}

# ---------- Phase 2: AI ----------

TAMIL_PROBLEM = "எனக்கு இரண்டு நாட்களாக தலைவலி மற்றும் காய்ச்சல் உள்ளது."


def run_async(coro):
    """Run a coroutine from a synchronous test."""
    import asyncio

    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _reset_ai_provider():
    """Each test gets a fresh provider/circuit-breaker (they are lru_cached)."""
    from app.providers.ai import reset_ai_provider_cache

    reset_ai_provider_cache()
    yield
    reset_ai_provider_cache()


def grant_ai_consent(client, patient, granted: bool = True):
    return client.put(f"{API}/patients/me/ai-consent", json={"granted": granted}, headers=patient.h)


@pytest.fixture
def consented_patient(client, make_patient):
    """A patient who has explicitly opted in to AI processing."""
    patient = make_patient()
    assert grant_ai_consent(client, patient).status_code == 200
    return patient


def create_problem(client, patient, text: str = TAMIL_PROBLEM, language: str = "ta"):
    r = client.post(
        f"{API}/patients/me/current-problems", json={"text": text, "language": language}, headers=patient.h
    )
    assert r.status_code == 201, r.text
    return r.json()


def process_record(client, patient, record_id: str):
    return client.post(f"{API}/patients/me/records/{record_id}/ai-process", headers=patient.h)


@pytest.fixture
def patient_with_ai(client, consented_patient):
    """Patient + a Tamil current problem that has been through the pipeline."""
    from types import SimpleNamespace

    record = create_problem(client, consented_patient)
    processed = process_record(client, consented_patient, record["id"])
    assert processed.status_code == 200, processed.text
    return SimpleNamespace(patient=consented_patient, record=record, ai=processed.json())
