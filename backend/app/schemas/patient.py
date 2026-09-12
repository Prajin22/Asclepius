import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.core.languages import LanguageCode
from app.models.enums import RecordSource, RecordStatus, RecordType, Sex
from app.schemas.common import LongText, ORMModel, Phone, ShortText


class PatientProfileOut(ORMModel):
    id: uuid.UUID
    display_name: str
    date_of_birth: date | None
    age: int | None = None
    sex: Sex
    phone: str | None
    preferred_language: LanguageCode
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    emergency_notes: str | None
    ai_processing_consent: bool
    ai_consent_updated_at: datetime | None
    updated_at: datetime


class PatientProfileUpdate(BaseModel):
    """PUT semantics: fields omitted are left unchanged; explicit null clears."""

    display_name: ShortText | None = None
    date_of_birth: date | None = None
    sex: Sex | None = None
    phone: Phone | None = None
    preferred_language: LanguageCode | None = None
    emergency_contact_name: str | None = Field(default=None, max_length=120)
    emergency_contact_phone: Phone | None = None
    emergency_notes: str | None = Field(default=None, max_length=2000)

    @field_validator("date_of_birth")
    @classmethod
    def _dob_sane(cls, v: date | None) -> date | None:
        if v is not None and (v > date.today() or v.year < 1900):
            raise ValueError("Date of birth is not plausible")
        return v


class MedicalRecordOut(ORMModel):
    id: uuid.UUID
    type: RecordType
    title: str | None
    content: str
    source: RecordSource
    source_language: LanguageCode
    status: RecordStatus
    created_at: datetime
    updated_at: datetime


class MedicalRecordCreate(BaseModel):
    type: RecordType
    title: ShortText | None = None
    content: str = Field(default="", max_length=10000)
    source_language: LanguageCode
    status: RecordStatus = RecordStatus.ACTIVE


class MedicalRecordUpdate(BaseModel):
    title: ShortText | None = None
    content: str | None = Field(default=None, max_length=10000)
    source_language: LanguageCode | None = None
    status: RecordStatus | None = None


class CurrentProblemCreate(BaseModel):
    """'What are you experiencing?' — stored verbatim, no interpretation."""

    text: LongText
    language: LanguageCode
