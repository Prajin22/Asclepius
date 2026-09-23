import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status
from pydantic import BaseModel

from app.api.deps import DB, Ctx, CurrentDoctor, DirectoryUser, DoctorAccount
from app.api.v1.files import document_file_response, page_image_response
from app.core.languages import LanguageCode
from app.providers.ai import get_ai_provider
from app.models.enums import ConsultationStatus
from app.schemas.consultation import (
    AssessmentUpdate,
    CaseView,
    DeclineRequest,
    DoctorQueueItem,
    PrescriptionCreate,
    PrescriptionOut,
)
from app.schemas.doctor import DoctorAccountOut, DoctorDetails, DoctorProfileUpdate, DoctorPublicOut
from app.schemas.summary import CaseSummaryOut
from app.services import (
    case_summary,
    consultation_service,
    doctor_service,
    document_pipeline,
    presenters,
)

# ----- doctor's own workspace -----
me_router = APIRouter(prefix="/doctors/me", tags=["doctor"])


class ConsultationStatusOut(BaseModel):
    id: uuid.UUID
    status: ConsultationStatus


@me_router.get("/profile", response_model=DoctorAccountOut)
def get_my_profile(doctor: DoctorAccount) -> DoctorAccountOut:
    """Open before approval, so an applicant can see where their application stands."""
    return presenters.doctor_account(doctor)


@me_router.put("/profile", response_model=DoctorAccountOut)
def update_my_profile(data: DoctorProfileUpdate, doctor: CurrentDoctor, db: DB) -> DoctorAccountOut:
    return presenters.doctor_account(doctor_service.update_profile(db, doctor, data, doctor.user))


@me_router.put("/application", response_model=DoctorAccountOut)
def update_my_application(data: DoctorDetails, doctor: DoctorAccount, db: DB, ctx: Ctx) -> DoctorAccountOut:
    """Correct the details an admin reviews. The application goes back to pending."""
    return presenters.doctor_account(doctor_service.update_application(db, doctor, data, doctor.user, ctx))


@me_router.get("/consultations", response_model=list[DoctorQueueItem])
def my_consultations(
    doctor: CurrentDoctor, db: DB, status_: Annotated[list[ConsultationStatus] | None, Query(alias="status")] = None
) -> list[DoctorQueueItem]:
    return consultation_service.doctor_queue(db, doctor, set(status_) if status_ else None)


@me_router.get("/consultations/{consultation_id}", response_model=CaseView)
def case_view(consultation_id: uuid.UUID, doctor: CurrentDoctor, db: DB, ctx: Ctx) -> CaseView:
    return consultation_service.doctor_case_view(db, doctor, doctor.user, consultation_id, ctx)


@me_router.post("/consultations/{consultation_id}/accept", response_model=CaseView)
def accept(consultation_id: uuid.UUID, doctor: CurrentDoctor, db: DB, ctx: Ctx) -> CaseView:
    c = consultation_service.doctor_action(db, doctor, doctor.user, consultation_id, "accept", ctx=ctx)
    return consultation_service.build_case_view(db, c)


@me_router.post("/consultations/{consultation_id}/decline", response_model=ConsultationStatusOut)
def decline(
    consultation_id: uuid.UUID, doctor: CurrentDoctor, db: DB, ctx: Ctx, data: DeclineRequest | None = None
) -> ConsultationStatusOut:
    c = consultation_service.doctor_action(
        db, doctor, doctor.user, consultation_id, "decline", reason=data.reason if data else None, ctx=ctx
    )
    return ConsultationStatusOut(id=c.id, status=c.status)


@me_router.post("/consultations/{consultation_id}/complete", response_model=CaseView)
def complete(consultation_id: uuid.UUID, doctor: CurrentDoctor, db: DB, ctx: Ctx) -> CaseView:
    c = consultation_service.doctor_action(db, doctor, doctor.user, consultation_id, "complete", ctx=ctx)
    return consultation_service.build_case_view(db, c)


@me_router.put("/consultations/{consultation_id}/assessment", response_model=CaseView)
def update_assessment(consultation_id: uuid.UUID, data: AssessmentUpdate, doctor: CurrentDoctor, db: DB) -> CaseView:
    c = consultation_service.set_assessment(db, doctor, doctor.user, consultation_id, data.doctor_assessment)
    return consultation_service.build_case_view(db, c)


@me_router.post(
    "/consultations/{consultation_id}/prescriptions", response_model=PrescriptionOut, status_code=status.HTTP_201_CREATED
)
def create_prescription(
    consultation_id: uuid.UUID, data: PrescriptionCreate, doctor: CurrentDoctor, db: DB, ctx: Ctx
) -> PrescriptionOut:
    rx = consultation_service.create_prescription(db, doctor, doctor.user, consultation_id, data, ctx)
    return presenters.prescription(rx)


@me_router.post("/consultations/{consultation_id}/summary", response_model=CaseSummaryOut)
async def generate_case_summary(
    consultation_id: uuid.UUID, doctor: CurrentDoctor, db: DB, ctx: Ctx
) -> CaseSummaryOut:
    """Organise the information this patient shared, for this doctor, right now.

    Reuses a stored summary when nothing shared has changed. Every gate —
    ownership, status, the patient's AI consent, the budget — is checked before
    any bundle is built, so a request that should not happen sends nothing.
    """
    state = await case_summary.generate(db, doctor, doctor.user, consultation_id, ctx)
    return case_summary.present(state, get_ai_provider())


@me_router.get("/consultations/{consultation_id}/summary", response_model=CaseSummaryOut)
def read_case_summary(
    consultation_id: uuid.UUID, doctor: CurrentDoctor, db: DB, ctx: Ctx
) -> CaseSummaryOut:
    """The stored summary, judged against the information as it stands now.

    Never generates. `stale` here means the shared information changed after the
    summary was made — the doctor is told, rather than shown an old answer as a
    current one.
    """
    state = case_summary.get_state(db, doctor, consultation_id)
    if state.summary is not None:
        case_summary.record_view(
            db, doctor.user, consultation_service.get_doctor_consultation(db, doctor, consultation_id),
            state.summary, ctx,
        )
    return case_summary.present(state, get_ai_provider())


@me_router.get("/consultations/{consultation_id}/documents/{document_id}/file")
def shared_document_file(
    consultation_id: uuid.UUID, document_id: uuid.UUID, doctor: CurrentDoctor, db: DB, ctx: Ctx
) -> Response:
    doc = consultation_service.doctor_shared_document(db, doctor, doctor.user, consultation_id, document_id, ctx)
    return document_file_response(doc)


@me_router.get("/consultations/{consultation_id}/documents/{document_id}/pages/{page_number}/image")
def shared_document_page_image(
    consultation_id: uuid.UUID,
    document_id: uuid.UUID,
    page_number: Annotated[int, Path(ge=1, le=10_000)],
    doctor: CurrentDoctor,
    db: DB,
    ctx: Ctx,
) -> Response:
    """A page of a document the patient shared in this consultation — and nothing else."""
    doc = consultation_service.doctor_shared_document(
        db, doctor, doctor.user, consultation_id, document_id, ctx,
        action="document.page_viewed_by_doctor", details={"page": page_number},
    )
    return page_image_response(document_pipeline.page_image_png(doc, page_number))


# ----- public directory ("Find care") -----
directory_router = APIRouter(prefix="/doctors", tags=["directory"])


@directory_router.get("", response_model=list[DoctorPublicOut])
def search_doctors(
    _: DirectoryUser,
    db: DB,
    q: Annotated[str | None, Query(max_length=100)] = None,
    specialization: Annotated[str | None, Query(max_length=120)] = None,
    language: LanguageCode | None = None,
) -> list[DoctorPublicOut]:
    return [presenters.doctor_public(d) for d in doctor_service.search_directory(db, q, specialization, language)]


@directory_router.get("/{doctor_id}", response_model=DoctorPublicOut)
def get_doctor(doctor_id: uuid.UUID, _: DirectoryUser, db: DB) -> DoctorPublicOut:
    return presenters.doctor_public(doctor_service.get_doctor(db, doctor_id))
