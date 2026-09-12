from fastapi import APIRouter

from app.api.v1 import admin, ai, auth, doctors, document_ai, messages, meta, patients

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(meta.router)
api_router.include_router(ai.router)  # before patients: /patients/me/ai* are more specific
api_router.include_router(document_ai.router)  # before patients: /patients/me/documents/{id}/... are more specific
api_router.include_router(patients.router)
api_router.include_router(doctors.me_router)  # before the directory's /doctors/{id}
api_router.include_router(doctors.directory_router)
api_router.include_router(messages.router)
api_router.include_router(admin.router)
