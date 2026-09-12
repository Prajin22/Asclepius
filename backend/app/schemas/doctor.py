import uuid

from pydantic import BaseModel, EmailStr, Field

from app.core.languages import LanguageCode
from app.schemas.auth import Password
from app.schemas.common import ORMModel, Phone, ShortText


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


class DoctorProfileUpdate(BaseModel):
    name: ShortText | None = None
    specialization: ShortText | None = None
    qualification: ShortText | None = None
    clinic_name: str | None = Field(default=None, max_length=200)
    clinic_address: str | None = Field(default=None, max_length=1000)
    phone: Phone | None = None
    languages: list[LanguageCode] | None = Field(default=None, max_length=12)
    is_accepting_consultations: bool | None = None


class DoctorCreate(BaseModel):
    """Admin-only doctor onboarding."""

    email: EmailStr
    password: Password
    name: ShortText
    specialization: ShortText
    qualification: ShortText
    registration_identifier: ShortText
    clinic_name: str | None = Field(default=None, max_length=200)
    clinic_address: str | None = Field(default=None, max_length=1000)
    phone: Phone | None = None
    languages: list[LanguageCode] = Field(default_factory=lambda: [LanguageCode.EN], max_length=12)
