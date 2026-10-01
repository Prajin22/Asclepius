from fastapi import APIRouter

from app.api.v1 import (
    admin,
    ai,
    auth,
    conversations,
    doctors,
    document_ai,
    messages,
    meta,
    patients,
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

    # IP-SAKTI Sahayak mounts no routes of its own in Phase 1: its shell needs
    # only sign-in and metadata. Its routes arrive with the phases that build them.
    return api_router
