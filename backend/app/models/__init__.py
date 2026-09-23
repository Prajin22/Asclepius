"""Import every model so Alembic and `Base.metadata` see the full schema."""

from app.models.ai import AIArtifact, AIExtractedFact
from app.models.audit import AuditEvent
from app.models.consultation import (
    Consultation,
    ConsultationMessage,
    ConsultationShare,
    Prescription,
    PrescriptionItem,
)
from app.models.doctor import DoctorLanguage, DoctorProfile
from app.models.document import DocumentExtraction, DocumentPage
from app.models.medical import MedicalDocument, MedicalRecord
from app.models.patient import PatientProfile
from app.models.summary import ConsultationSummary
from app.models.user import User

__all__ = [
    "AIArtifact",
    "AIExtractedFact",
    "AuditEvent",
    "Consultation",
    "ConsultationMessage",
    "ConsultationShare",
    "ConsultationSummary",
    "DoctorLanguage",
    "DoctorProfile",
    "DocumentExtraction",
    "DocumentPage",
    "MedicalDocument",
    "MedicalRecord",
    "PatientProfile",
    "Prescription",
    "PrescriptionItem",
    "User",
]
