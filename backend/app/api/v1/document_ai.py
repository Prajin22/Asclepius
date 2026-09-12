"""Patient document intelligence endpoints (Phase 3). All logic lives in the service layer."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Response

from app.api.deps import DB, Ctx, CurrentPatient
from app.api.v1.files import page_image_response
from app.schemas.document_ai import DocumentProcessingOut
from app.services import document_pipeline, document_presenters, document_service

router = APIRouter(prefix="/patients/me/documents", tags=["patient-document-ai"])

PageNumber = Annotated[int, Path(ge=1, le=10_000)]


@router.post("/{document_id}/process", response_model=DocumentProcessingOut)
async def process_document(document_id: uuid.UUID, patient: CurrentPatient, db: DB, ctx: Ctx) -> DocumentProcessingOut:
    """Read the document page by page and extract reviewable items. The file is unchanged."""
    document = document_service.get_own_document(db, patient, document_id)
    outcome = await document_pipeline.process_document(db, patient, patient.user, document, ctx)
    return document_presenters.processing_out(outcome)


@router.get("/{document_id}/extraction", response_model=DocumentProcessingOut)
def document_extraction(document_id: uuid.UUID, patient: CurrentPatient, db: DB) -> DocumentProcessingOut:
    document = document_service.get_own_document(db, patient, document_id)
    return document_presenters.processing_out(document_pipeline.get_document_state(db, patient, document))


@router.get("/{document_id}/pages/{page_number}/image")
def page_image(document_id: uuid.UUID, page_number: PageNumber, patient: CurrentPatient, db: DB) -> Response:
    """One page of the original document as an image, for seeing evidence in place."""
    document = document_service.get_own_document(db, patient, document_id)
    return page_image_response(document_pipeline.page_image_png(document, page_number))
