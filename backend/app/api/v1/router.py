from fastapi import APIRouter

from app.api.v1 import (
    admin,
    ai,
    auth,
    classification,
    conversations,
    corpus,
    doctors,
    document_ai,
    messages,
    meta,
    patients,
    products,
)
from app.core.product import Product


def build_api_router(product: Product) -> APIRouter:
    """The API one product serves (D-077).

    Shared routes — sign-in, the signed-in account, metadata — are always
    mounted. Each product's own routes are mounted only for that product, so a
    route that belongs to the other product does not exist here at all: it is a
    404, not a 403 behind a check someone could forget.
    """
    api_router = APIRouter(prefix="/api/v1")
    api_router.include_router(auth.router)
    api_router.include_router(meta.router)

    if product == Product.CAREBRIDGE:
        # Unchanged from before the product boundary existed, in the same order.
        api_router.include_router(auth.registration_router)
        api_router.include_router(ai.router)  # before patients: /patients/me/ai* are more specific
        api_router.include_router(document_ai.router)  # before patients: /patients/me/documents/{id}/... are more specific
        api_router.include_router(conversations.router)  # before patients: /patients/me/conversations* are more specific
        api_router.include_router(patients.router)
        api_router.include_router(doctors.me_router)  # before the directory's /doctors/{id}
        api_router.include_router(doctors.directory_router)
        api_router.include_router(messages.router)
        api_router.include_router(admin.router)

    if product == Product.IP_SAKTI:
        # Phase 2: the curator's legal source corpus. Nothing in it answers or
        # searches — those arrive with the phases that build them.
        api_router.include_router(corpus.router)
        # Phase 3: product profiles and the formulation classifier. Still nothing
        # that answers a legal question.
        api_router.include_router(products.router)
        api_router.include_router(classification.router)
        api_router.include_router(classification.tree_router)
    return api_router
