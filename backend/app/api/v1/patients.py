import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Response, UploadFile, status

from app.api.deps import DB, Ctx, CurrentPatient
from app.api.v1.files import document_file_response
from app.core.config import get_settings
from app.core.languages import LanguageCode
from app.models.enums import DocumentType, RecordType
from app.providers.storage import get_storage
from app.schemas.consultation import (
    ConsultationRequestCreate,
    ConsultationSummary,
    PatientConsultationDetail,
    PatientDashboard,
    PrescriptionOut,
)
from app.schemas.document import MedicalDocumentOut
from app.schemas.patient import (
    CurrentProblemCreate,
    MedicalRecordCreate,
    MedicalRecordOut,
    MedicalRecordUpdate,
    PatientProfileOut,
    PatientProfileUpdate,
)
from app.services import consultation_service, document_service, patient_service, presenters

router = APIRouter(prefix="/patients/me", tags=["patient"])


# ---------- profile ----------


@router.get("/profile", response_model=PatientProfileOut)
def get_profile(patient: CurrentPatient) -> PatientProfileOut:
    return presenters.patient_profile(patient)


@router.put("/profile", response_model=PatientProfileOut)
def update_profile(data: PatientProfileUpdate, patient: CurrentPatient, db: DB) -> PatientProfileOut:
    return presenters.patient_profile(patient_service.update_profile(db, patient, data, patient.user))


@router.get("/dashboard", response_model=PatientDashboard)
def dashboard(patient: CurrentPatient, db: DB) -> PatientDashboard:
    return patient_service.dashboard(db, patient)


# ---------- health records ----------


@router.get("/records", response_model=list[MedicalRecordOut])
def list_records(patient: CurrentPatient, db: DB, type: RecordType | None = None) -> list[MedicalRecordOut]:
    return [MedicalRecordOut.model_validate(r) for r in patient_service.list_records(db, patient, type)]


@router.post("/records", response_model=MedicalRecordOut, status_code=status.HTTP_201_CREATED)
def create_record(data: MedicalRecordCreate, patient: CurrentPatient, db: DB) -> MedicalRecordOut:
    return MedicalRecordOut.model_validate(patient_service.create_record(db, patient, data, patient.user))


@router.post("/current-problems", response_model=MedicalRecordOut, status_code=status.HTTP_201_CREATED)
def create_current_problem(data: CurrentProblemCreate, patient: CurrentPatient, db: DB) -> MedicalRecordOut:
    """Stores the patient's own words verbatim. No interpretation in Phase 1."""
    return MedicalRecordOut.model_validate(patient_service.create_current_problem(db, patient, data, patient.user))


@router.patch("/records/{record_id}", response_model=MedicalRecordOut)
def update_record(record_id: uuid.UUID, data: MedicalRecordUpdate, patient: CurrentPatient, db: DB) -> MedicalRecordOut:
    return MedicalRecordOut.model_validate(patient_service.update_record(db, patient, record_id, data, patient.user))


@router.delete("/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(record_id: uuid.UUID, patient: CurrentPatient, db: DB) -> Response:
    patient_service.delete_record(db, patient, record_id, patient.user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- documents ----------


@router.get("/documents", response_model=list[MedicalDocumentOut])
def list_documents(patient: CurrentPatient, db: DB) -> list[MedicalDocumentOut]:
    return [MedicalDocumentOut.model_validate(d) for d in document_service.list_documents(db, patient)]


@router.post("/documents", response_model=MedicalDocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    patient: CurrentPatient,
    db: DB,
    file: Annotated[UploadFile, File()],
    document_type: Annotated[DocumentType, Form()],
    source_language: Annotated[LanguageCode | None, Form()] = None,
    title: Annotated[str | None, Form(max_length=200)] = None,
) -> MedicalDocumentOut:
    max_bytes = get_settings().max_upload_bytes
    data = file.file.read(max_bytes + 1)  # read at most limit+1 to detect oversize
    doc = document_service.upload_document(
        db,
        get_storage(),
        patient=patient,
        actor=patient.user,
        filename=file.filename,
        declared_mime=file.content_type,
        data=data,
        document_type=document_type,
        source_language=source_language,
        title=title,
        max_bytes=max_bytes,
    )
    return MedicalDocumentOut.model_validate(doc)


@router.get("/documents/{document_id}", response_model=MedicalDocumentOut)
def get_document(document_id: uuid.UUID, patient: CurrentPatient, db: DB) -> MedicalDocumentOut:
    return MedicalDocumentOut.model_validate(document_service.get_own_document(db, patient, document_id))


@router.get("/documents/{document_id}/file")
def get_document_file(document_id: uuid.UUID, patient: CurrentPatient, db: DB) -> Response:
    return document_file_response(document_service.get_own_document(db, patient, document_id))


# ---------- consultations ----------


@router.get("/consultations", response_model=list[ConsultationSummary])
def list_consultations(patient: CurrentPatient, db: DB) -> list[ConsultationSummary]:
    return [presenters.consultation_summary(c) for c in consultation_service.list_patient_consultations(db, patient)]


@router.post("/consultations", response_model=PatientConsultationDetail, status_code=status.HTTP_201_CREATED)
def request_consultation(
    data: ConsultationRequestCreate, patient: CurrentPatient, db: DB, ctx: Ctx
) -> PatientConsultationDetail:
    c = consultation_service.request_consultation(db, patient, patient.user, data, ctx)
    return consultation_service.patient_detail(c)


@router.get("/consultations/{consultation_id}", response_model=PatientConsultationDetail)
def get_consultation(consultation_id: uuid.UUID, patient: CurrentPatient, db: DB) -> PatientConsultationDetail:
    return consultation_service.patient_detail(consultation_service.get_patient_consultation(db, patient, consultation_id))


@router.post("/consultations/{consultation_id}/cancel", response_model=PatientConsultationDetail)
def cancel_consultation(
    consultation_id: uuid.UUID, patient: CurrentPatient, db: DB, ctx: Ctx
) -> PatientConsultationDetail:
    c = consultation_service.patient_cancel(db, patient, patient.user, consultation_id, ctx)
    return consultation_service.patient_detail(c)


@router.get("/prescriptions", response_model=list[PrescriptionOut])
def list_prescriptions(
    patient: CurrentPatient, db: DB, consultation_id: Annotated[uuid.UUID | None, Query()] = None
) -> list[PrescriptionOut]:
    rxs = consultation_service.list_patient_prescriptions(db, patient)
    if consultation_id:
        rxs = [rx for rx in rxs if rx.consultation_id == consultation_id]
    return [presenters.prescription(rx) for rx in rxs]
