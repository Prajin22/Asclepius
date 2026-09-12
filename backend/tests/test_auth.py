from sqlalchemy import select

from app.models import AuditEvent, User
from tests.conftest import API, PASSWORD, auth


def test_register_creates_patient_with_hashed_password(client, db):
    r = client.post(
        f"{API}/auth/register",
        json={"email": "Asha@Example.com", "password": PASSWORD, "display_name": "Asha", "preferred_language": "hi"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["role"] == "patient"
    assert body["user"]["email"] == "asha@example.com"
    user = db.scalar(select(User).where(User.email == "asha@example.com"))
    assert user.password_hash != PASSWORD
    assert user.password_hash.startswith("$2")


def test_login_is_case_insensitive_and_returns_token(client, make_patient):
    make_patient(email="ravi@example.com")
    r = client.post(f"{API}/auth/login", json={"email": "RAVI@example.com", "password": PASSWORD})
    assert r.status_code == 200
    me = client.get(f"{API}/auth/me", headers=auth(r.json()["access_token"]))
    assert me.status_code == 200
    assert me.json()["display_name"] == "Arun Kumar"


def test_wrong_password_rejected_and_audited(client, db, make_patient):
    make_patient(email="ravi@example.com")
    r = client.post(f"{API}/auth/login", json={"email": "ravi@example.com", "password": "wrong-password"})
    assert r.status_code == 401
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "auth.login_failed")) is not None


def test_unknown_email_rejected_with_same_message(client, make_patient):
    make_patient(email="ravi@example.com")
    a = client.post(f"{API}/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    b = client.post(f"{API}/auth/login", json={"email": "ravi@example.com", "password": "bad-password"})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]


def test_duplicate_email_conflict(client, make_patient):
    make_patient(email="dup@example.com")
    r = client.post(
        f"{API}/auth/register", json={"email": "DUP@example.com", "password": PASSWORD, "display_name": "X"}
    )
    assert r.status_code == 409


def test_weak_password_rejected(client):
    r = client.post(f"{API}/auth/register", json={"email": "a@example.com", "password": "short", "display_name": "A"})
    assert r.status_code == 422


def test_invalid_and_missing_tokens(client):
    assert client.get(f"{API}/auth/me").status_code == 401
    assert client.get(f"{API}/auth/me", headers=auth("not-a-jwt")).status_code == 401


def test_token_signed_with_other_secret_rejected(client, make_patient):
    import jwt

    p = make_patient()
    payload = {"sub": p.user_id, "role": "doctor", "iat": 0, "exp": 9999999999}
    forged = jwt.encode(payload, "an-attacker-controlled-secret-of-sufficient-length", algorithm="HS256")
    assert client.get(f"{API}/auth/me", headers=auth(forged)).status_code == 401


def test_deactivated_user_cannot_use_token(client, db, make_patient):
    p = make_patient()
    user = db.get(User, __import__("uuid").UUID(p.user_id))
    user.is_active = False
    db.commit()
    assert client.get(f"{API}/auth/me", headers=p.h).status_code == 401
