"""Import every model so Alembic and `Base.metadata` see the full schema."""

from app.models.ai import AIArtifact, AIExtractedFact
from app.models.audit import AuditEvent
from app.models.conversation import (
    ConversationCandidateFact,
    ConversationResponse,
    ConversationSession,
    ConversationSkip,
)
from app.models.corpus import (
    CorpusChunk,
    CorpusDocument,
    CorpusPage,
    Instrument,
    Provision,
    ProvisionStatusEvent,
    ProvisionVersion,
)
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
    "ConversationCandidateFact",
    "ConversationResponse",
    "ConversationSession",
    "ConversationSkip",
    "CorpusChunk",
    "CorpusDocument",
    "CorpusPage",
    "DoctorLanguage",
    "DoctorProfile",
    "DocumentExtraction",
    "DocumentPage",
    "Instrument",
    "MedicalDocument",
    "MedicalRecord",
    "PatientProfile",
    "Prescription",
    "PrescriptionItem",
    "Provision",
    "ProvisionStatusEvent",
    "ProvisionVersion",
    "User",
]
