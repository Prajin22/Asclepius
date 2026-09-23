from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.languages import LANGUAGES, AISupport, LanguageCode
from app.providers.ai import build_ai_provider
from app.providers.ai.errors import AIError
from app.providers.ai.prompts import PROMPT_VERSIONS
from app.schemas.ai import AIStatusOut

router = APIRouter(prefix="/meta", tags=["meta"])


class LanguageOut(BaseModel):
    code: LanguageCode
    english_name: str
    native_name: str
    script: str
    ui_available: bool
    ai_support: AISupport


@router.get("/languages", response_model=list[LanguageOut])
def languages() -> list[LanguageOut]:
    return [LanguageOut(**vars(info)) for info in LANGUAGES.values()]


@router.get("/ai", response_model=AIStatusOut)
def ai_status() -> AIStatusOut:
    """Describes the AI configuration. Never exposes credentials."""
    settings = get_settings()
    try:
        provider = build_ai_provider(settings)
        name, model, external = provider.name, provider.model, provider.is_external
    except AIError:
        # Misconfigured (e.g. no key): report it without leaking anything.
        name, model, external = settings.effective_ai_provider, settings.ai_model, True
    return AIStatusOut(
        provider=name,
        model=model,
        demo_mode=settings.demo_mode,
        is_external=external,
        # Derived from the prompts that exist, so a new capability cannot ship
        # without appearing here. Phase 3's transcription was missing while this
        # was a hand-written list.
        enabled_features=sorted(PROMPT_VERSIONS),
        prompt_versions=PROMPT_VERSIONS,
    )
