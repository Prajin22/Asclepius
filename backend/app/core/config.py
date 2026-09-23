import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

_INSECURE_SECRETS = {"", "replace-with-a-long-random-string", "change-me"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"

    database_url: str = "postgresql+psycopg://carebridge:carebridge_dev_password@localhost:5432/carebridge"

    jwt_secret: str = "replace-with-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 120

    # NoDecode: dotenv values are passed to the validator as written, so the
    # documented comma-separated form works (pydantic-settings would otherwise
    # try to JSON-decode it and fail at startup).
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    storage_provider: str = "local"
    storage_local_root: str = "./storage"
    max_upload_bytes: int = 10 * 1024 * 1024

    # ---------- AI ----------
    # DEMO_MODE forces the deterministic local provider: no external call can
    # happen, whatever AI_PROVIDER says. The demo cannot fail on a missing key,
    # a quota, or provider latency.
    demo_mode: bool = True
    ai_provider: str = "mock"
    ai_model: str = ""
    ai_timeout_seconds: float = 20.0
    ai_max_attempts: int = 2  # 1 retry
    ai_circuit_failure_threshold: int = 3
    ai_circuit_reset_seconds: float = 60.0
    ai_cache_enabled: bool = True

    # Per-patient limits. A run is one pipeline pass that actually called the
    # provider (cache hits are free and do not count). Set 0 to disable a limit.
    ai_rate_limit_per_hour: int = 20
    ai_rate_limit_per_day: int = 100
    # Estimated spend per patient over a rolling 24h, in USD.
    ai_daily_cost_limit_usd: float = 1.0

    # ---------- Case summary (Phase 4) ----------
    # How many times one consultation's case summary may actually be generated.
    # Separate from the patient's run limits because a doctor starts this, and a
    # doctor regenerating must not exhaust the allowance a patient needs for
    # their own record. Cache hits cost nothing and do not count. Set 0 to disable.
    summary_per_consultation_limit: int = 10

    # ---------- Documents (Phase 3) ----------
    # Pages read per processing request. Each page with text is one AI run.
    document_processing_max_pages: int = 10
    # How pages without an embedded text layer (scans, photos) are read:
    #   auto     offline OCR in DEMO_MODE; otherwise the AI provider's vision if it
    #            has one, else offline OCR
    #   local    always the offline OCR engine (never leaves this machine)
    #   provider always the AI provider's vision (external; needs consent)
    #   none     text-layer PDFs only
    ocr_engine: str = "auto"
    # A PDF page with fewer embedded characters than this is treated as a scan.
    ocr_min_text_layer_chars: int = 20
    document_render_scale: float = 2.0
    document_max_pixels: int = 40_000_000

    # Credentials stay server-side and are never serialised into a response.
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None

    # Base URLs are overridable so tests can point at a stub transport.
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    # Optional price override (USD per million tokens) when a model is not in
    # app/providers/ai/pricing.py.
    ai_price_input_per_mtok: float | None = None
    ai_price_output_per_mtok: float | None = None

    @field_validator("database_url", mode="before")
    @classmethod
    def _psycopg_driver(cls, v: object) -> object:
        """Managed hosts hand out `postgres://` URLs; this project uses psycopg 3.

        Without this, SQLAlchemy would look for psycopg2, which is not installed.
        """
        if isinstance(v, str):
            for prefix in ("postgres://", "postgresql://"):
                if v.startswith(prefix):
                    return "postgresql+psycopg://" + v[len(prefix) :]
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            text = v.strip()
            if text.startswith("["):
                return json.loads(text)
            return [o.strip() for o in text.split(",") if o.strip()]
        return v

    @field_validator(
        "ai_price_input_per_mtok",
        "ai_price_output_per_mtok",
        "openai_api_key",
        "anthropic_api_key",
        "gemini_api_key",
        mode="before",
    )
    @classmethod
    def _blank_is_unset(cls, v: object) -> object:
        """`KEY=` in a .env file means "not configured", not an empty value."""
        return None if isinstance(v, str) and not v.strip() else v

    @model_validator(mode="after")
    def _refuse_insecure_secret_outside_dev(self) -> "Settings":
        if self.app_env not in ("development", "test") and (
            self.jwt_secret in _INSECURE_SECRETS or len(self.jwt_secret) < 32
        ):
            raise ValueError("JWT_SECRET must be a strong secret outside development/test")
        return self

    @property
    def storage_root_path(self) -> Path:
        p = Path(self.storage_local_root)
        return p if p.is_absolute() else (BACKEND_DIR / p).resolve()

    @property
    def effective_ai_provider(self) -> str:
        """The provider actually used. DEMO_MODE pins everything to `mock`."""
        return "mock" if self.demo_mode else self.ai_provider

    def api_key_for(self, provider: str) -> str | None:
        secret = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "gemini": self.gemini_api_key,
        }.get(provider)
        if secret is None:
            return None
        # `model_copy(update=...)` can bypass validation and leave a plain str.
        return secret.get_secret_value() if isinstance(secret, SecretStr) else str(secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
