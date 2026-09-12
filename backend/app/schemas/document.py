import uuid
from datetime import datetime

from app.core.languages import LanguageCode
from app.models.enums import DocumentStatus, DocumentType
from app.schemas.common import ORMModel


class MedicalDocumentOut(ORMModel):
    id: uuid.UUID
    file_name: str
    mime_type: str
    size_bytes: int
    document_type: DocumentType
    title: str | None
    source_language: LanguageCode | None
    status: DocumentStatus
    uploaded_at: datetime
