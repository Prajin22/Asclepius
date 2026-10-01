"""The product boundary: one codebase, CareBridge or IP-SAKTI Sahayak (D-077–D-079).

Both applications are built in this one process with `create_app(product)`,
over the same test database. Each test is about one promise:

* PRODUCT=carebridge serves exactly what it served before the boundary existed,
  plus one read-only metadata endpoint;
* PRODUCT=ip_sakti serves no healthcare route; its own routes are sign-in,
  metadata, the curator's source corpus (Phase 2) and product profiles with
  the formulation classifier (Phase 3) — and nothing that answers or searches;
* each product accepts its own roles and no others, and a token works only in
  the product that issued it;
* each product has its own AI policy, and IP-SAKTI's permits nothing yet;
* DEMO_MODE still pins the offline provider, whichever the product.
"""

import inspect
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.ai_policy import CAPABILITIES, CAREBRIDGE_POLICY, IP_SAKTI_POLICY, PROMPT_FOR_CAPABILITY
from app.core.config import REPO_ROOT, Settings, get_settings
from app.core.languages import LanguageCode
from app.core.product import Product
from app.core.product_config import PRODUCTS, product_config
from app.core.security import hash_password
from app.main import create_app
from app.models import AuditEvent, Consultation, ConsultationMessage, MedicalRecord, PatientProfile, User
from app.models.enums import CareBridgeRole, UserRole
from app.providers.ai import MockAIProvider, PolicyRestrictedProvider, build_ai_provider
from app.providers.ai.base import AIProvider
from app.providers.ai.policy import restrict_to_policy
from app.providers.ai.prompts import PROMPT_VERSIONS
from app.sakti import seed as sakti_seed
from app.services.errors import AICapabilityNotPermitted
from tests.ai_stubs import RecordingProvider
from tests.conftest import API, PASSWORD, auth, run_async

SNAPSHOT = Path(__file__).parent / "data" / "carebridge_api_operations.json"
METHODS = ("get", "post", "put", "patch", "delete")
#: Areas that belong to later IP-SAKTI phases. Not one may exist yet. ("corpus"
#: and "provision" left this list in Phase 2, "classif" in Phase 3.)
FUTURE_LEGAL_WORDS = ("answer", "ask", "retriev", "search", "embed", "citation", "escalat", "curator",
                      "facilitator", "product-profile", "abs", "tkdl")


def operations(app) -> set[str]:
    return {f"{m.upper()} {path}" for path, ops in app.openapi()["paths"].items() for m in ops if m in METHODS}


@pytest.fixture
def sakti_client():
    with TestClient(create_app(Product.IP_SAKTI)) as c:
        yield c


def make_account(db, role: UserRole, email: str) -> User:
    user = User(role=role, email=email, password_hash=hash_password(PASSWORD))
    db.add(user)
    db.commit()
    return user


def login(client, email: str):
    return client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})


# --------------------------------------------------------------------------
# the setting
# --------------------------------------------------------------------------


def test_an_unset_product_is_carebridge(monkeypatch):
    monkeypatch.delenv("PRODUCT", raising=False)
    assert Settings(_env_file=None).product == Product.CAREBRIDGE


def test_the_documented_example_configuration_is_carebridge(monkeypatch):
    monkeypatch.delenv("PRODUCT", raising=False)
    assert Settings(_env_file=REPO_ROOT / ".env.example").product == Product.CAREBRIDGE


@pytest.mark.parametrize("value", ["ipsakti", "IP-SAKTI", "health", ""])
def test_an_unknown_product_stops_the_application(monkeypatch, value):
    monkeypatch.setenv("PRODUCT", value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_the_application_takes_its_product_from_the_setting():
    assert get_settings().product == Product.CAREBRIDGE  # pinned in conftest
    assert create_app().state.product_config.product == Product.CAREBRIDGE
    assert create_app(Product.IP_SAKTI).state.product_config.product == Product.IP_SAKTI


# --------------------------------------------------------------------------
# 1. CareBridge is unchanged
# --------------------------------------------------------------------------


def test_carebridge_serves_exactly_its_previous_api_plus_product_metadata():
    before = set(json.loads(SNAPSHOT.read_text(encoding="utf-8"))["operations"])
    now = operations(create_app(Product.CAREBRIDGE))
    assert now - before == {"GET /api/v1/meta/product"}, "CareBridge gained an endpoint it did not have"
    assert before - now == set(), "CareBridge lost an endpoint it used to serve"


def test_carebridge_api_keeps_its_title():
    assert create_app(Product.CAREBRIDGE).openapi()["info"]["title"] == "CareBridge API"


def test_carebridge_roles_still_work(client, make_patient, make_doctor, make_admin):
    patient, doctor, admin = make_patient(), make_doctor(), make_admin()
    assert client.get(f"{API}/patients/me/profile", headers=patient.h).status_code == 200
    assert client.get(f"{API}/doctors/me/profile", headers=doctor.h).status_code == 200
    assert client.get(f"{API}/admin/doctors", headers=admin.h).status_code == 200
    assert client.get(f"{API}/patients/me/profile", headers=doctor.h).status_code == 403


def test_carebridge_registration_still_works(client):
    r = client.post(f"{API}/auth/register", json={
        "email": "new@example.com", "password": PASSWORD, "display_name": "New", "preferred_language": "ta"})
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "patient"


# --------------------------------------------------------------------------
# 2–4. IP-SAKTI serves only the shell's routes
# --------------------------------------------------------------------------


#: Phase 2: the curator's legal source corpus (D-081).
IP_SAKTI_CORPUS_OPERATIONS = {
    "GET /api/v1/corpus/authorities",
    "GET /api/v1/corpus/instruments",
    "POST /api/v1/corpus/instruments",
    "GET /api/v1/corpus/instruments/{instrument_id}",
    "POST /api/v1/corpus/instruments/{instrument_id}/provisions",
    "GET /api/v1/corpus/sources",
    "POST /api/v1/corpus/sources",
    "GET /api/v1/corpus/sources/{source_id}",
    "GET /api/v1/corpus/sources/{source_id}/original",
    "POST /api/v1/corpus/sources/{source_id}/parse",
    "GET /api/v1/corpus/sources/{source_id}/text",
    "GET /api/v1/corpus/sources/{source_id}/diff",
    "POST /api/v1/corpus/sources/{source_id}/submit",
    "POST /api/v1/corpus/sources/{source_id}/approve",
    "POST /api/v1/corpus/sources/{source_id}/reject",
    "POST /api/v1/corpus/sources/{source_id}/versions",
    "GET /api/v1/corpus/versions/{version_id}",
    "PATCH /api/v1/corpus/versions/{version_id}",
    "GET /api/v1/corpus/versions/{version_id}/diff",
    "POST /api/v1/corpus/versions/{version_id}/submit",
    "POST /api/v1/corpus/versions/{version_id}/approve",
    "POST /api/v1/corpus/versions/{version_id}/reject",
    "POST /api/v1/corpus/versions/{version_id}/status-events",
    "GET /api/v1/corpus/review-queue",
    "GET /api/v1/corpus/drafts",
}


#: Phase 3: product profiles and the formulation classifier (D-087).
IP_SAKTI_CLASSIFIER_OPERATIONS = {
    "GET /api/v1/products",
    "POST /api/v1/products",
    "GET /api/v1/products/{product_id}",
    "PATCH /api/v1/products/{product_id}",
    "GET /api/v1/products/{product_id}/classifications",
    "POST /api/v1/classifications",
    "GET /api/v1/classifications/{session_id}",
    "POST /api/v1/classifications/{session_id}/responses",
    "POST /api/v1/classifications/{session_id}/restart",
    "POST /api/v1/classifications/{session_id}/confirm",
    "POST /api/v1/classifications/{session_id}/reject",
    "GET /api/v1/classification-tree",
    "GET /api/v1/classification-tree/{version}",
    "POST /api/v1/classification-tree/{version}/references/{slot_id}",
}


def test_ip_sakti_serves_only_its_shell_corpus_and_classifier():
    assert operations(create_app(Product.IP_SAKTI)) == {
        "POST /api/v1/auth/login",
        "GET /api/v1/auth/me",
        "GET /api/v1/meta/languages",
        "GET /api/v1/meta/ai",
        "GET /api/v1/meta/product",
        "GET /health",
    } | IP_SAKTI_CORPUS_OPERATIONS | IP_SAKTI_CLASSIFIER_OPERATIONS


def test_ip_sakti_mounts_no_healthcare_route():
    for op in operations(create_app(Product.IP_SAKTI)):
        path = op.split(" ", 1)[1]
        for healthcare in ("patients", "doctors", "consultations", "prescriptions", "records", "documents",
                           "conversations", "register", "admin"):
            assert healthcare not in path, f"{op} is a healthcare route"


def test_ip_sakti_mounts_no_route_of_a_later_phase():
    for op in operations(create_app(Product.IP_SAKTI)):
        for word in FUTURE_LEGAL_WORDS:
            assert word not in op.lower(), f"{op} belongs to a later phase"


@pytest.mark.parametrize("method,path", [
    ("get", "/patients/me/profile"),
    ("get", "/doctors"),
    ("get", "/doctors/me/consultations"),
    ("get", "/admin/doctors"),
    ("post", "/auth/register"),
    ("post", "/auth/register-doctor"),
    ("post", "/patients/me/conversations"),
])
def test_a_healthcare_route_does_not_exist_in_ip_sakti(sakti_client, method, path):
    assert getattr(sakti_client, method)(f"{API}{path}").status_code == 404


def test_ip_sakti_api_has_its_own_title():
    info = create_app(Product.IP_SAKTI).openapi()["info"]
    assert info["title"] == "IP-SAKTI Sahayak API"
    assert "not give legal advice" in info["description"]


# --------------------------------------------------------------------------
# product metadata
# --------------------------------------------------------------------------


def test_product_metadata_describes_carebridge(client):
    body = client.get(f"{API}/meta/product").json()
    assert body["product"] == "carebridge"
    assert body["roles"] == ["admin", "doctor", "patient"]
    assert body["ai_policy"]["id"] == "carebridge_health_v1"
    assert body["ai_policy"]["capabilities"] == sorted(CAPABILITIES)
    assert body["demo_mode"] is True


def test_product_metadata_describes_ip_sakti(sakti_client):
    body = sakti_client.get(f"{API}/meta/product").json()
    assert body["product"] == "ip_sakti"
    assert body["display_name"] == "IP-SAKTI Sahayak"
    assert body["roles"] == ["admin", "curator", "facilitator", "user"]
    assert body["ai_policy"]["id"] == "ip_sakti_legal_information_v1"
    assert body["ai_policy"]["document"] == "docs/IP_SAKTI_AI_POLICY.md"
    assert body["ai_policy"]["capabilities"] == []
    assert "no_legal_advice" in body["ai_policy"]["rules"]
    assert body["demo_mode"] is True


def test_product_metadata_carries_no_secret(sakti_client):
    text = sakti_client.get(f"{API}/meta/product").text.lower()
    for secret in ("key", "secret", "password", "token", "database"):
        assert secret not in text


# --------------------------------------------------------------------------
# 5–6. roles
# --------------------------------------------------------------------------


def test_each_product_accepts_exactly_its_own_roles():
    assert PRODUCTS[Product.CAREBRIDGE].roles == {UserRole.PATIENT, UserRole.DOCTOR, UserRole.ADMIN}
    assert PRODUCTS[Product.IP_SAKTI].roles == {UserRole.USER, UserRole.FACILITATOR, UserRole.CURATOR, UserRole.ADMIN}
    # Every role belongs to some product; only `admin` belongs to both.
    shared = PRODUCTS[Product.CAREBRIDGE].roles & PRODUCTS[Product.IP_SAKTI].roles
    assert shared == {UserRole.ADMIN}
    assert set(UserRole) == PRODUCTS[Product.CAREBRIDGE].roles | PRODUCTS[Product.IP_SAKTI].roles


def test_carebridge_role_values_are_unchanged():
    assert [UserRole.PATIENT.value, UserRole.DOCTOR.value, UserRole.ADMIN.value] == ["patient", "doctor", "admin"]


def test_healthcare_tables_still_accept_only_carebridge_roles():
    """Widening the shared role vocabulary must not widen a healthcare table."""
    assert {r.value for r in CareBridgeRole} == {"patient", "doctor", "admin"}
    assert Consultation.__table__.c.cancelled_by_role.type.enums == ["patient", "doctor", "admin"]
    assert ConsultationMessage.__table__.c.sender_role.type.enums == ["patient", "doctor", "admin"]
    assert User.__table__.c.role.type.enums == ["patient", "doctor", "admin", "user", "facilitator", "curator"]


@pytest.mark.parametrize("role", [UserRole.USER, UserRole.FACILITATOR, UserRole.CURATOR, UserRole.ADMIN])
def test_every_ip_sakti_role_can_sign_in_to_ip_sakti(sakti_client, db, role):
    make_account(db, role, f"{role.value}@sakti.example.com")
    r = login(sakti_client, f"{role.value}@sakti.example.com")
    assert r.status_code == 200, r.text
    me = sakti_client.get(f"{API}/auth/me", headers=auth(r.json()["access_token"])).json()
    assert me["user"]["role"] == role.value
    # No healthcare profile is created or looked for.
    assert me["profile_id"] is None and me["doctor_approval"] is None


@pytest.mark.parametrize("role", [UserRole.PATIENT, UserRole.DOCTOR])
def test_a_carebridge_account_cannot_sign_in_to_ip_sakti(sakti_client, db, role):
    user = make_account(db, role, f"{role.value}@carebridge.example.com")
    r = login(sakti_client, user.email)
    assert r.status_code == 401
    assert r.json()["code"] == "authentication_failed"
    # Indistinguishable from a wrong password — nothing about the other product leaks.
    wrong = sakti_client.post(f"{API}/auth/login", json={"email": user.email, "password": "Wrong-pass1"})
    assert wrong.json() == r.json()
    refused = db.scalars(select(AuditEvent).where(AuditEvent.action == "auth.login_failed",
                                                  AuditEvent.resource_id == str(user.id))).all()
    assert {"reason": "role_not_in_product"} in [e.details for e in refused]


@pytest.mark.parametrize("role", [UserRole.USER, UserRole.FACILITATOR, UserRole.CURATOR])
def test_an_ip_sakti_account_cannot_sign_in_to_carebridge(client, db, role):
    make_account(db, role, f"{role.value}@sakti.example.com")
    assert login(client, f"{role.value}@sakti.example.com").status_code == 401


def test_a_token_works_only_in_the_product_that_issued_it(client, sakti_client, db):
    """`admin` exists in both products, so the role alone cannot keep a token in
    its own product. The product claim does."""
    make_account(db, UserRole.ADMIN, "admin@both.example.com")
    carebridge_token = login(client, "admin@both.example.com").json()["access_token"]
    sakti_token = login(sakti_client, "admin@both.example.com").json()["access_token"]

    assert client.get(f"{API}/auth/me", headers=auth(carebridge_token)).status_code == 200
    assert sakti_client.get(f"{API}/auth/me", headers=auth(sakti_token)).status_code == 200
    assert sakti_client.get(f"{API}/auth/me", headers=auth(carebridge_token)).status_code == 401
    assert client.get(f"{API}/admin/doctors", headers=auth(sakti_token)).status_code == 401


def test_a_token_from_before_the_boundary_still_works_in_carebridge_only(client, sakti_client, db, make_patient):
    """Sessions issued before the product claim existed carry none, and were all CareBridge's."""
    settings = get_settings()
    admin = make_account(db, UserRole.ADMIN, "legacy@both.example.com")

    def legacy(user: User) -> str:
        now = datetime.now(UTC)
        return jwt.encode({"sub": str(user.id), "role": user.role.value, "iat": now,
                           "exp": now + timedelta(minutes=5), "jti": uuid.uuid4().hex},
                          settings.jwt_secret, algorithm=settings.jwt_algorithm)

    assert client.get(f"{API}/admin/doctors", headers=auth(legacy(admin))).status_code == 200
    assert sakti_client.get(f"{API}/auth/me", headers=auth(legacy(admin))).status_code == 401


def test_an_ip_sakti_role_reaches_no_carebridge_route_even_with_a_forged_token(client, db):
    """Defence in depth: a validly signed token for an IP-SAKTI role is still not
    a CareBridge session."""
    settings = get_settings()
    user = make_account(db, UserRole.USER, "forged@sakti.example.com")
    now = datetime.now(UTC)
    token = jwt.encode({"sub": str(user.id), "role": "user", "product": "carebridge", "iat": now,
                        "exp": now + timedelta(minutes=5), "jti": uuid.uuid4().hex},
                       settings.jwt_secret, algorithm=settings.jwt_algorithm)
    assert client.get(f"{API}/auth/me", headers=auth(token)).status_code == 401


# --------------------------------------------------------------------------
# 8. AI policy follows the product
# --------------------------------------------------------------------------


def test_each_product_selects_its_own_ai_policy():
    assert product_config(Product.CAREBRIDGE).ai_policy is CAREBRIDGE_POLICY
    assert product_config(Product.IP_SAKTI).ai_policy is IP_SAKTI_POLICY


def test_the_capability_list_covers_the_whole_provider_interface():
    """A provider method no policy has ruled on could run anywhere."""
    methods = {name for name, fn in inspect.getmembers(AIProvider, inspect.iscoroutinefunction)
               if not name.startswith("_") and name != "aclose"}
    assert methods == set(CAPABILITIES)
    assert set(PROMPT_FOR_CAPABILITY) == set(CAPABILITIES)
    assert set(PROMPT_FOR_CAPABILITY.values()) == set(PROMPT_VERSIONS)


def test_carebridge_policy_permits_what_carebridge_uses_and_ip_sakti_permits_nothing():
    assert CAREBRIDGE_POLICY.permits_everything
    assert IP_SAKTI_POLICY.capabilities == frozenset()
    for capability in CAPABILITIES:
        assert not IP_SAKTI_POLICY.permits(capability)


def test_carebridge_gets_its_provider_exactly_as_before():
    provider = build_ai_provider(Settings(_env_file=None, product=Product.CAREBRIDGE))
    assert type(provider) is MockAIProvider


def test_ip_sakti_gets_a_provider_that_refuses_every_capability():
    provider = build_ai_provider(Settings(_env_file=None, product=Product.IP_SAKTI))
    assert isinstance(provider, PolicyRestrictedProvider)
    assert provider.supports_vision is False
    calls = {
        "detect_language": lambda: provider.detect_language("x"),
        "normalize_to_english": lambda: provider.normalize_to_english("x", LanguageCode.EN),
        "extract_medical_information": lambda: provider.extract_medical_information("x", LanguageCode.EN),
        "transcribe_document_image": lambda: provider.transcribe_document_image(b"", 1),
        "summarize_case": lambda: provider.summarize_case("{}"),
    }
    assert set(calls) == set(CAPABILITIES)
    for capability, call in calls.items():
        with pytest.raises(AICapabilityNotPermitted, match=capability):
            run_async(call())


def test_a_refused_capability_never_reaches_the_provider():
    """Refused before the call: no text is sent, nothing is spent."""
    inner = RecordingProvider()
    restricted = restrict_to_policy(inner, IP_SAKTI_POLICY)
    for call in (lambda: restricted.detect_language("text"),
                 lambda: restricted.normalize_to_english("text", LanguageCode.EN),
                 lambda: restricted.extract_medical_information("text", LanguageCode.EN)):
        with pytest.raises(AICapabilityNotPermitted):
            run_async(call())
    assert inner.calls == []
    # And under CareBridge's policy the very same provider is used unwrapped.
    assert restrict_to_policy(inner, CAREBRIDGE_POLICY) is inner


def test_ai_status_reports_only_what_the_product_permits(client, sakti_client):
    carebridge = client.get(f"{API}/meta/ai").json()
    assert carebridge["enabled_features"] == sorted(PROMPT_VERSIONS)  # as before
    assert carebridge["prompt_versions"] == PROMPT_VERSIONS
    sakti = sakti_client.get(f"{API}/meta/ai").json()
    assert sakti["enabled_features"] == []
    assert sakti["prompt_versions"] == {}


def test_ip_sakti_policy_forbids_advice_fields_and_states_every_boundary():
    for field in ("recommendation", "advice", "next_steps"):
        assert field in IP_SAKTI_POLICY.forbidden_answer_fields
    for rule in ("no_legal_advice", "no_generated_statutory_text", "no_fabricated_citations",
                 "no_invented_section_numbers", "no_unsupported_claims_of_current_law",
                 "no_impersonating_lawyer_or_authority", "source_grounding_required",
                 "abstain_or_escalate_when_uncertain"):
        assert rule in IP_SAKTI_POLICY.rules


def test_every_policy_rule_is_written_down_in_its_document():
    for policy in (CAREBRIDGE_POLICY, IP_SAKTI_POLICY):
        document = REPO_ROOT / policy.document
        assert document.exists(), policy.document
    text = (REPO_ROOT / IP_SAKTI_POLICY.document).read_text(encoding="utf-8")
    for rule in IP_SAKTI_POLICY.rules:
        assert f"`{rule}`" in text, f"{rule} is enforced in code but not written in the policy"


# --------------------------------------------------------------------------
# 9. DEMO_MODE
# --------------------------------------------------------------------------


@pytest.mark.parametrize("product", list(Product))
def test_demo_mode_pins_the_offline_provider_in_both_products(product):
    settings = Settings(_env_file=None, product=product, demo_mode=True, ai_provider="openai")
    assert settings.effective_ai_provider == "mock"
    provider = build_ai_provider(settings)
    assert provider.name == "mock" and provider.is_external is False


def test_ip_sakti_reports_demo_mode(sakti_client):
    assert sakti_client.get(f"{API}/meta/ai").json()["demo_mode"] is True


# --------------------------------------------------------------------------
# seed
# --------------------------------------------------------------------------


def test_ip_sakti_seed_creates_one_synthetic_account_per_role_and_nothing_else(db, capsys):
    sakti_seed.seed(db)
    users = {u.email: u.role for u in db.scalars(select(User))}
    assert users == {email: role for role, email, _ in sakti_seed.DEMO_ACCOUNTS}
    assert all(email.endswith("@ipsakti.demo") for email in users)
    for healthcare in (PatientProfile, MedicalRecord, Consultation):
        assert db.scalar(select(func.count()).select_from(healthcare)) == 0
    assert "No legal content is seeded" in capsys.readouterr().out

    sakti_seed.seed(db)  # idempotent
    assert db.scalar(select(func.count()).select_from(User)) == len(sakti_seed.DEMO_ACCOUNTS)


def test_the_seed_command_seeds_the_configured_product(db, monkeypatch):
    import app.seed as seed_module

    monkeypatch.setattr(seed_module, "get_settings", lambda: Settings(_env_file=None, product=Product.IP_SAKTI))
    assert seed_module.main([]) == 0
    db.expire_all()
    roles = {u.role for u in db.scalars(select(User))}
    assert roles == {UserRole.USER, UserRole.FACILITATOR, UserRole.CURATOR, UserRole.ADMIN}
    assert db.scalar(select(func.count()).select_from(PatientProfile)) == 0


def test_ip_sakti_demo_accounts_sign_in(sakti_client, db):
    sakti_seed.seed(db)
    for role, email, password in sakti_seed.DEMO_ACCOUNTS:
        r = sakti_client.post(f"{API}/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, email
        assert r.json()["user"]["role"] == role.value
