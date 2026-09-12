import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints

from app.core.languages import LanguageCode
from app.models.enums import DoctorApproval
from app.schemas.auth import Password
from app.schemas.common import ORMModel, Phone, ShortText

# Limits match the column widths, so overlong input is a 422 here, not a database error.
Text120 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
RegistrationNumber = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
ReviewNote = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class DoctorPublicOut(ORMModel):
    """What any patient may see in the directory."""

    id: uuid.UUID
    name: str
    specialization: str
    qualification: str
    registration_identifier: str
    clinic_name: str | None
    clinic_address: str | None
    phone: str | None
    languages: list[LanguageCode]
    is_accepting_consultations: bool


class DoctorAccountOut(DoctorPublicOut):
    """A doctor's own profile, including where their application stands."""

    approval_status: DoctorApproval
    approval_note: str | None
    reviewed_at: datetime | None


class DoctorApplicationOut(DoctorAccountOut):
    """What an admin reviews before approving a doctor."""

    email: str
    applied_at: datetime
    # Another doctor account uses the same registration number.
    registration_conflict: bool


class DoctorProfileUpdate(BaseModel):
    name: Text120 | None = None
    specialization: Text120 | None = None
    qualification: ShortText | None = None
    clinic_name: str | None = Field(default=None, max_length=200)
    clinic_address: str | None = Field(default=None, max_length=1000)
    phone: Phone | None = None
    languages: list[LanguageCode] | None = Field(default=None, max_length=12)
    is_accepting_consultations: bool | None = None


class DoctorDetails(BaseModel):
    """The professional details an admin checks before approving a doctor."""

    name: Text120
    specialization: Text120
    qualification: ShortText
    registration_identifier: RegistrationNumber
    clinic_name: str | None = Field(default=None, max_length=200)
    clinic_address: str | None = Field(default=None, max_length=1000)
    phone: Phone | None = None
    languages: list[LanguageCode] = Field(default_factory=lambda: [LanguageCode.EN], min_length=1, max_length=12)


class DoctorCreate(DoctorDetails):
    """Admin onboarding. The admin vouches for the doctor, so the account is approved at once."""

    email: EmailStr
    password: Password


class DoctorApplication(DoctorDetails):
    """Doctor self sign-up. The account starts pending and sees no patient data until an admin approves it."""

    email: EmailStr
    password: Password


class DoctorRejectRequest(BaseModel):
    """Shown to the applicant, so write it for them."""

    reason: ReviewNote
