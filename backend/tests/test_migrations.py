"""Migrations apply cleanly and match the ORM models (PostgreSQL only).

Set MIGRATION_TEST_DATABASE_URL to an empty PostgreSQL database whose name
contains "test", e.g. .../carebridge_migrations_test
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

URL = os.environ.get("MIGRATION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="MIGRATION_TEST_DATABASE_URL not set")

BACKEND = Path(__file__).resolve().parents[1]


def _config() -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.attributes["database_url"] = URL
    return cfg


def _head(cfg: Config) -> str:
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(cfg).get_current_head()


def test_upgrade_check_downgrade():
    assert URL and "test" in URL.rsplit("/", 1)[-1]
    cfg = _config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(URL)
    tables = set(inspect(engine).get_table_names())
    assert {"users", "patient_profiles", "consultations", "consultation_shares", "prescriptions",
            "ai_artifacts", "audit_events", "consultation_summaries",
            "conversation_sessions", "conversation_responses",
            "conversation_candidate_facts", "conversation_skips"} <= tables
    command.check(cfg)  # raises if models and migrations have drifted
    command.downgrade(cfg, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    engine.dispose()


def test_phase_4_revision_is_reversible_on_its_own():
    """0007 can be stepped down and back up without disturbing 0001-0006.

    Summaries are derived data — every source they organise lives in its own
    table — so dropping the revision must lose nothing else.
    """
    cfg = _config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(URL)

    command.downgrade(cfg, "0006")
    tables = set(inspect(engine).get_table_names())
    assert "consultation_summaries" not in tables
    assert {"consultations", "ai_artifacts", "medical_records", "document_pages"} <= tables

    command.upgrade(cfg, "0007")
    assert "consultation_summaries" in set(inspect(engine).get_table_names())

    # `check` compares the models against the database, so it only means
    # anything at head. 0007 stopped being head when 0008 was added.
    command.upgrade(cfg, "head")
    command.check(cfg)

    command.downgrade(cfg, "base")
    engine.dispose()


def test_phase_5_revision_is_reversible_on_its_own():
    """0008 can be stepped down and back up without disturbing 0001-0007.

    A conversation is a workflow. Health records confirmed out of one belong to
    the patient and live in `medical_records`, so dropping the revision must
    leave them standing.
    """
    cfg = _config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(URL)

    command.downgrade(cfg, "0007")
    tables = set(inspect(engine).get_table_names())
    for dropped in (
        "conversation_sessions",
        "conversation_responses",
        "conversation_candidate_facts",
    ):
        assert dropped not in tables
    assert {"medical_records", "consultation_summaries", "ai_artifacts"} <= tables

    command.upgrade(cfg, "head")
    assert {
        "conversation_sessions",
        "conversation_responses",
        "conversation_candidate_facts",
    } <= set(inspect(engine).get_table_names())
    command.check(cfg)

    command.downgrade(cfg, "base")
    engine.dispose()


def _check_definition(engine, name: str) -> str:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = :n"), {"n": name}
        ).scalar_one()


def test_phase_5b_revision_is_reversible_on_its_own():
    """0009 steps down and back up without disturbing 0001-0008.

    Autogenerate cannot see value changes on a VARCHAR + CHECK enum, so
    `alembic check` passing proves nothing about the three new sections. The
    constraint definitions are read back from PostgreSQL instead.
    """
    cfg = _config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(URL)
    for name in ("ck_conversation_sessions_conversation_section", "ck_conversation_responses_response_section"):
        definition = _check_definition(engine, name)
        for section in ("radiation_or_spread", "aggravating_factors", "relieving_factors"):
            assert section in definition, (name, section)
    columns = {c["name"] for c in inspect(engine).get_columns("conversation_responses")}
    assert {"declined", "reason_code", "trigger_question_id", "predicate_id"} <= columns
    assert "skipped" not in columns

    command.downgrade(cfg, "0008")
    tables = set(inspect(engine).get_table_names())
    assert "conversation_skips" not in tables
    assert {"conversation_sessions", "conversation_responses", "conversation_candidate_facts",
            "medical_records", "consultation_summaries"} <= tables
    columns = {c["name"] for c in inspect(engine).get_columns("conversation_responses")}
    assert "skipped" in columns and "declined" not in columns
    assert "radiation_or_spread" not in _check_definition(engine, "ck_conversation_responses_response_section")

    command.upgrade(cfg, "head")
    assert "conversation_skips" in set(inspect(engine).get_table_names())
    command.check(cfg)
    command.downgrade(cfg, "base")
    engine.dispose()


def test_phase_5b_downgrade_refuses_to_destroy_patient_answers():
    """With a v2 conversation on record, stepping down to 0008 would either
    delete it or leave sections 0008 cannot hold. It refuses and changes nothing."""
    from sqlalchemy.orm import Session

    from app.models import ConversationSession, PatientProfile, User
    from app.models.enums import UserRole

    cfg = _config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(URL)
    with Session(engine) as s:
        user = User(role=UserRole.PATIENT, email="downgrade@example.com", password_hash="x")
        s.add(user)
        s.flush()
        patient = PatientProfile(user_id=user.id, display_name="Synthetic")
        s.add(patient)
        s.flush()
        s.add(ConversationSession(patient_id=patient.id, flow_id="history_general", flow_version=2))
        s.commit()

    with pytest.raises(RuntimeError, match="Refusing to downgrade 0009"):
        command.downgrade(cfg, "0008")
    # Nothing was changed: still at head, the conversation still there. (The
    # whole downgrade is one transaction, so the step above 0009 that did
    # succeed is rolled back with it.)
    assert "conversation_skips" in set(inspect(engine).get_table_names())
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == _head(cfg)
        assert conn.execute(text("SELECT COUNT(*) FROM conversation_sessions")).scalar_one() == 1

    # Removed deliberately, the downgrade goes through.
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users"))
    command.downgrade(cfg, "base")
    engine.dispose()


def test_ip_sakti_roles_revision_widens_only_the_shared_users_table():
    """ipsakti_0001 lets `users.role` hold the IP-SAKTI roles and touches nothing
    else: both healthcare role columns keep exactly the constraint 0001 gave them.
    Read back from PostgreSQL, since `alembic check` cannot see CHECK values."""
    cfg = _config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "ipsakti_0001")
    engine = create_engine(URL)

    carebridge_only = ("'patient'", "'doctor'", "'admin'")
    users = _check_definition(engine, "ck_users_user_role")
    for role in carebridge_only + ("'user'", "'facilitator'", "'curator'"):
        assert role in users
    for name in ("ck_consultations_cancelled_by_role", "ck_consultation_messages_sender_role"):
        definition = _check_definition(engine, name)
        assert all(role in definition for role in carebridge_only)
        for role in ("'user'", "'facilitator'", "'curator'"):
            assert role not in definition, f"{name} was widened"

    command.downgrade(cfg, "0009")
    users = _check_definition(engine, "ck_users_user_role")
    assert all(role in users for role in carebridge_only)
    assert "'facilitator'" not in users and "'curator'" not in users

    command.upgrade(cfg, "head")
    command.check(cfg)
    command.downgrade(cfg, "base")
    engine.dispose()


def test_ip_sakti_roles_downgrade_refuses_to_delete_accounts():
    from sqlalchemy.orm import Session

    from app.models import User
    from app.models.enums import UserRole

    cfg = _config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "ipsakti_0001")
    engine = create_engine(URL)
    with Session(engine) as s:
        s.add(User(role=UserRole.CURATOR, email="curator@downgrade.example.com", password_hash="x"))
        s.commit()

    with pytest.raises(RuntimeError, match="Refusing to downgrade ipsakti_0001"):
        command.downgrade(cfg, "0009")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "ipsakti_0001"
        assert conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 1

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users"))
    command.downgrade(cfg, "base")
    engine.dispose()


CORPUS_TABLES = {"instruments", "corpus_documents", "corpus_pages", "corpus_chunks", "provisions",
                 "provision_versions", "provision_status_events"}


def _corpus_triggers(engine) -> set[str]:
    with engine.connect() as conn:
        return set(conn.execute(text("SELECT tgname FROM pg_trigger WHERE tgname LIKE 'trg_%_immutable'")).scalars())


def test_ip_sakti_corpus_revision_adds_the_corpus_and_its_guards_and_nothing_else():
    """ipsakti_0002 adds seven tables and their immutability triggers, and is
    reversible on an empty corpus without disturbing anything before it."""
    cfg = _config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "ipsakti_0001")
    engine = create_engine(URL)
    before = set(inspect(engine).get_table_names())

    command.upgrade(cfg, "ipsakti_0002")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "ipsakti_0002"
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) - before == CORPUS_TABLES
    assert _corpus_triggers(engine) == {f"trg_{t}_immutable" for t in CORPUS_TABLES}
    for table in CORPUS_TABLES:
        lane = next(c for c in inspector.get_columns(table) if c["name"] == "lane") if table != "corpus_pages" else None
        assert table == "corpus_pages" or lane["nullable"] is False

    command.downgrade(cfg, "ipsakti_0001")
    assert set(inspect(engine).get_table_names()) == before
    assert _corpus_triggers(engine) == set()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM pg_proc WHERE proname = 'corpus_refuse_update'")).scalar() == 0
    command.upgrade(cfg, "head")
    command.check(cfg)
    command.downgrade(cfg, "base")
    engine.dispose()


def test_ip_sakti_corpus_triggers_hold_in_a_migrated_database():
    """The triggers the migration installs refuse what the model's create_all
    triggers refuse: no lane change, no edit of an approved row."""
    cfg = _config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(URL)
    with engine.begin() as conn:
        user = conn.execute(text(
            "INSERT INTO users (id, role, email, password_hash) VALUES (gen_random_uuid(), 'curator', "
            "'c@migrate.example.com', 'x') RETURNING id")).scalar_one()
        instrument = conn.execute(text(
            "INSERT INTO instruments (id, lane, instrument_type, title, issued_by, created_by_user_id) "
            "VALUES (gen_random_uuid(), 'india', 'other', 'Synthetic', 'Test', :u) RETURNING id"), {"u": user}).scalar_one()
    with pytest.raises(Exception, match="immutable"), engine.begin() as conn:
        conn.execute(text("UPDATE instruments SET lane = 'international' WHERE id = :i"), {"i": instrument})
    with pytest.raises(Exception, match="fk_provisions_instrument_lane"), engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO provisions (id, instrument_id, lane, locator, locator_type, created_by_user_id) "
            "VALUES (gen_random_uuid(), :i, 'international', '1', 'other', :u)"), {"i": instrument, "u": user})
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM instruments"))
        conn.execute(text("DELETE FROM users"))
    command.downgrade(cfg, "base")
    engine.dispose()


def test_ip_sakti_corpus_downgrade_refuses_to_drop_curated_records():
    cfg = _config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "ipsakti_0002")
    engine = create_engine(URL)
    with engine.begin() as conn:
        user = conn.execute(text(
            "INSERT INTO users (id, role, email, password_hash) VALUES (gen_random_uuid(), 'curator', "
            "'c@downgrade.example.com', 'x') RETURNING id")).scalar_one()
        conn.execute(text(
            "INSERT INTO instruments (id, lane, instrument_type, title, issued_by, created_by_user_id) "
            "VALUES (gen_random_uuid(), 'international', 'other', 'Synthetic', 'Test', :u)"), {"u": user})

    with pytest.raises(RuntimeError, match="Refusing to downgrade ipsakti_0002"):
        command.downgrade(cfg, "ipsakti_0001")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "ipsakti_0002"
        assert conn.execute(text("SELECT COUNT(*) FROM instruments")).scalar_one() == 1

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM instruments"))
        conn.execute(text("DELETE FROM users"))
    command.downgrade(cfg, "base")
    engine.dispose()


CLASSIFIER_TABLES = {"product_profiles", "classification_sessions", "classification_answers",
                     "classification_outcomes", "classifier_reference_links"}


def test_ip_sakti_classifier_revision_adds_only_its_own_tables():
    """ipsakti_0003 adds five tables and their triggers, touches no healthcare
    or corpus table, and is reversible while no user data exists."""
    cfg = _config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "ipsakti_0002")
    engine = create_engine(URL)
    before = set(inspect(engine).get_table_names())
    constraints_before = {
        t: {c["name"] for c in inspect(engine).get_foreign_keys(t)} for t in ("users", "provision_versions")
    }

    command.upgrade(cfg, "ipsakti_0003")
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) - before == CLASSIFIER_TABLES
    for table in CLASSIFIER_TABLES:
        targets = {fk["referred_table"] for fk in inspector.get_foreign_keys(table)}
        assert not targets & {"patient_profiles", "doctor_profiles", "consultations", "medical_records"}, table
    assert {t: {c["name"] for c in inspector.get_foreign_keys(t)} for t in constraints_before} == constraints_before
    with engine.connect() as conn:
        triggers = set(conn.execute(text("SELECT tgname FROM pg_trigger WHERE tgname LIKE 'trg_%_final'")).scalars())
    assert triggers == {"trg_classification_outcomes_final", "trg_classifier_reference_links_final",
                        "trg_classification_sessions_final", "trg_classification_answers_final"}
    command.check(cfg)

    command.downgrade(cfg, "ipsakti_0002")
    assert set(inspect(engine).get_table_names()) == before
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM pg_proc WHERE proname = 'sakti_refuse_final_update'")).scalar() == 0
    command.upgrade(cfg, "head")
    command.check(cfg)
    command.downgrade(cfg, "base")
    engine.dispose()


def test_ip_sakti_classifier_outcomes_never_carry_a_category_from_unknown():
    cfg = _config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(URL)
    with engine.begin() as conn:
        user = conn.execute(text(
            "INSERT INTO users (id, role, email, password_hash) VALUES (gen_random_uuid(), 'user', "
            "'u@migrate.example.com', 'x') RETURNING id")).scalar_one()
        product = conn.execute(text(
            "INSERT INTO product_profiles (id, owner_user_id, name, ingredients, markers, revision) "
            "VALUES (gen_random_uuid(), :u, 'Synthetic', '[]', '[]', 1) RETURNING id"), {"u": user}).scalar_one()
        session = conn.execute(text(
            "INSERT INTO classification_sessions (id, product_id, owner_user_id, classifier_id, tree_version, "
            "tree_fingerprint, status, product_revision, product_snapshot, revision) VALUES (gen_random_uuid(), :p, :u, "
            "'ip_sakti_formulation', 1, 'x', 'requires_information', 1, '{}', 1) RETURNING id"),
            {"p": product, "u": user}).scalar_one()
    with pytest.raises(Exception, match="category_only_when_determined"), engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO classification_outcomes (id, session_id, sequence, kind, category, stop_node_id, path, "
            "answers_sha256, tree_version, tree_fingerprint, \"references\") VALUES (gen_random_uuid(), :s, 1, "
            "'requires_information', 'classical', 'purpose', '[]', 'x', 1, 'x', '[]')"), {"s": session})

    with pytest.raises(RuntimeError, match="Refusing to downgrade ipsakti_0003"):
        command.downgrade(cfg, "ipsakti_0002")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM classification_sessions"))
        conn.execute(text("DELETE FROM product_profiles"))
        conn.execute(text("DELETE FROM users"))
    command.downgrade(cfg, "base")
    engine.dispose()
