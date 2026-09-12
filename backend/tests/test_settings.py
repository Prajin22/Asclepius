"""Configuration must load from the documented files, exactly as a new developer uses them."""

from app.core.config import REPO_ROOT, Settings


import pytest


@pytest.fixture(autouse=True)
def _file_values_win(monkeypatch):
    # conftest pins these in the process environment, which would otherwise take
    # precedence over the file under test.
    for name in ("CORS_ORIGINS", "DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)


def test_env_example_loads():
    """README setup is `cp .env.example .env`; that file must parse."""
    settings = Settings(_env_file=REPO_ROOT / ".env.example")
    assert settings.cors_origins == ["http://localhost:3000", "http://localhost:3001"]
    assert settings.demo_mode is True


def test_comma_separated_origins(tmp_path):
    env = tmp_path / ".env"
    env.write_text("CORS_ORIGINS=http://a.test, http://b.test\n", encoding="utf-8")
    assert Settings(_env_file=env).cors_origins == ["http://a.test", "http://b.test"]


def test_json_list_origins(tmp_path):
    env = tmp_path / ".env"
    env.write_text('CORS_ORIGINS=["http://a.test"]\n', encoding="utf-8")
    assert Settings(_env_file=env).cors_origins == ["http://a.test"]


@pytest.mark.parametrize(
    "given",
    [
        "postgres://user:pw@host.render.com:5432/asclepius",
        "postgresql://user:pw@host.render.com:5432/asclepius",
    ],
)
def test_managed_database_urls_get_the_psycopg_driver(tmp_path, given):
    """Render and similar hosts hand out postgres:// URLs; psycopg2 is not installed."""
    env = tmp_path / ".env"
    env.write_text(f"DATABASE_URL={given}\n", encoding="utf-8")
    assert Settings(_env_file=env).database_url.startswith("postgresql+psycopg://")


def test_an_explicit_driver_is_left_alone(tmp_path):
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=postgresql+psycopg://u:p@localhost:5432/db\n", encoding="utf-8")
    assert Settings(_env_file=env).database_url == "postgresql+psycopg://u:p@localhost:5432/db"


def test_blank_values_mean_not_configured(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "AI_PRICE_INPUT_PER_MTOK=\nAI_PRICE_OUTPUT_PER_MTOK=\nANTHROPIC_API_KEY=\n",
        encoding="utf-8",
    )
    settings = Settings(_env_file=env)
    assert settings.ai_price_input_per_mtok is None
    assert settings.ai_price_output_per_mtok is None
    assert settings.api_key_for("anthropic") is None
