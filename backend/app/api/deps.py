import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import DoctorProfile, PatientProfile, User
from app.models.enums import UserRole
from app.services.audit import RequestContext
from app.services.errors import DoctorNotApproved

_bearer = HTTPBearer(auto_error=False)

DB = Annotated[Session, Depends(get_db)]


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    db: DB, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise _unauthorized()
    try:
        payload = decode_access_token(creds.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise _unauthorized("Invalid or expired token") from None
    user = db.get(User, user_id)
    if user is None or not user.is_active or user.role.value != payload.get("role"):
        raise _unauthorized("Invalid or expired token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole):
    def _dep(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not permitted for this role")
        return user

    return _dep


PatientUser = Annotated[User, Depends(require_roles(UserRole.PATIENT))]
DoctorUser = Annotated[User, Depends(require_roles(UserRole.DOCTOR))]
AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
PatientOrDoctorUser = Annotated[User, Depends(require_roles(UserRole.PATIENT, UserRole.DOCTOR))]
DirectoryUser = Annotated[User, Depends(require_roles(UserRole.PATIENT, UserRole.ADMIN))]


def get_current_patient(db: DB, user: PatientUser) -> PatientProfile:
    profile = db.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id))
    if profile is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Patient profile missing")
    return profile


def get_doctor_account(db: DB, user: DoctorUser) -> DoctorProfile:
    """The signed-in doctor's own profile, whatever the state of their application."""
    profile = db.scalar(select(DoctorProfile).where(DoctorProfile.user_id == user.id))
    if profile is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Doctor profile missing")
    return profile


DoctorAccount = Annotated[DoctorProfile, Depends(get_doctor_account)]


def get_current_doctor(doctor: DoctorAccount) -> DoctorProfile:
    """An approved doctor. Every route that can reach patient data depends on this."""
    if not doctor.is_approved:
        raise DoctorNotApproved("An administrator has not approved this doctor account")
    return doctor


CurrentPatient = Annotated[PatientProfile, Depends(get_current_patient)]
CurrentDoctor = Annotated[DoctorProfile, Depends(get_current_doctor)]


def request_context(request: Request) -> RequestContext:
    return RequestContext(ip_address=request.client.host if request.client else None)


Ctx = Annotated[RequestContext, Depends(request_context)]
