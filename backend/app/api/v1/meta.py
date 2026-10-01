from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentProduct
from app.core.ai_policy import PROMPT_FOR_CAPABILITY
from app.core.config import get_settings
from app.core.product import Product
from app.core.languages import LANGUAGES, AISupport, LanguageCode
from app.providers.ai import build_ai_provider
from app.providers.ai.errors import AIError
from app.providers.ai.prompts import PROMPT_VERSIONS
from app.models.enums import UserRole
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


class AIPolicyOut(BaseModel):
    id: str
    #: The written policy, relative to the repository root.
    document: str
    rules: list[str]
    #: Provider capabilities this product may call. Empty means none.
    capabilities: list[str]


class ProductOut(BaseModel):
    """Which product this API serves. Public, read-only, credential-free."""

    product: Product
    display_name: str
    roles: list[UserRole]
    demo_mode: bool
    ai_policy: AIPolicyOut


@router.get("/product", response_model=ProductOut)
def product_info(product: CurrentProduct) -> ProductOut:
    """Lets a client confirm it is talking to the product it was built for (D-077)."""
    policy = product.ai_policy
    return ProductOut(
        product=product.product,
        display_name=product.display_name,
        roles=sorted(product.roles),
        demo_mode=get_settings().demo_mode,
        ai_policy=AIPolicyOut(
            id=policy.id,
            document=policy.document,
            rules=list(policy.rules),
            capabilities=sorted(policy.capabilities),
        ),
    )


@router.get("/ai", response_model=AIStatusOut)
def ai_status(product: CurrentProduct) -> AIStatusOut:
    """Describes the AI configuration. Never exposes credentials."""
    settings = get_settings()
    permitted = {
        PROMPT_FOR_CAPABILITY[c] for c in product.ai_policy.capabilities
    } & set(PROMPT_VERSIONS)
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
        # was a hand-written list. Only what this product's AI policy permits is
        # reported (D-079): CareBridge's permits every prompt, IP-SAKTI's none yet.
        enabled_features=sorted(permitted),
        prompt_versions={name: v for name, v in PROMPT_VERSIONS.items() if name in permitted},
    )
