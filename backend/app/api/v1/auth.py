from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import DB, Ctx, CurrentProduct, CurrentUser
from app.core.product_config import ProductConfig
from app.core.security import create_access_token
from app.models import DoctorProfile, PatientProfile, User
from app.schemas.auth import LoginRequest, MeResponse, PatientRegisterRequest, TokenResponse, UserOut
from app.schemas.doctor import DoctorApplication
from app.services import auth_service

#: Shared by both products: sign in, and who am I.
router = APIRouter(prefix="/auth", tags=["auth"])
#: CareBridge only: patient and doctor self-registration (D-077).
registration_router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User, product: ProductConfig) -> TokenResponse:
    token, expires_in = create_access_token(user.id, user.role.value, product.product.value)
    return TokenResponse(access_token=token, expires_in=expires_in, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: DB, ctx: Ctx, product: CurrentProduct) -> TokenResponse:
    user = auth_service.authenticate(db, data.email, data.password, ctx, allowed_roles=product.roles)
    return _token_response(user, product)


@registration_router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_patient(data: PatientRegisterRequest, db: DB, ctx: Ctx, product: CurrentProduct) -> TokenResponse:
    """Patient self-registration."""
    return _token_response(auth_service.register_patient(db, data, ctx), product)


@registration_router.post("/register-doctor", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def apply_as_doctor(data: DoctorApplication, db: DB, ctx: Ctx, product: CurrentProduct) -> TokenResponse:
    """Doctor sign-up. The account signs in at once but reaches no patient data until an admin approves it."""
    return _token_response(auth_service.apply_as_doctor(db, data, ctx), product)


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser, db: DB) -> MeResponse:
    patient = db.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id))
    doctor = db.scalar(select(DoctorProfile).where(DoctorProfile.user_id == user.id))
    profile = patient or doctor
    return MeResponse(
        user=UserOut.model_validate(user),
        profile_id=profile.id if profile else None,
        display_name=patient.display_name if patient else (doctor.name if doctor else None),
        doctor_approval=doctor.approval_status if doctor else None,
    )
