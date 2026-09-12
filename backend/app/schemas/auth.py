import uuid
from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.core.languages import LanguageCode
from app.core.security import BCRYPT_MAX_BYTES
from app.models.enums import UserRole
from app.schemas.common import ORMModel, ShortText


def _password_rules(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(v.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError(f"Password must be at most {BCRYPT_MAX_BYTES} bytes")
    return v


Password = Annotated[str, AfterValidator(_password_rules)]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class PatientRegisterRequest(BaseModel):
    email: EmailStr
    password: Password
    display_name: ShortText
    preferred_language: LanguageCode = LanguageCode.EN


class UserOut(ORMModel):
    id: uuid.UUID
    role: UserRole
    email: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class MeResponse(BaseModel):
    user: UserOut
    profile_id: uuid.UUID | None
    display_name: str | None
