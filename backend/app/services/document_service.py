"""Document upload validation and storage.

Defence in depth: declared MIME type allow-list + magic-byte sniffing +
extension allow-list + size limit + server-generated storage keys.
"""

import hashlib
import re
import unicodedata
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.languages import LanguageCode
from app.models import MedicalDocument, PatientProfile, User
from app.models.enums import DocumentStatus, DocumentType
from app.providers.storage import ObjectStorageProvider
from app.services import audit
from app.services.errors import InvalidInput, NotFound


@dataclass(frozen=True)
class AllowedType:
    extensions: tuple[str, ...]
    canonical_ext: str


ALLOWED_TYPES: dict[str, AllowedType] = {
    "application/pdf": AllowedType((".pdf",), ".pdf"),
    "image/jpeg": AllowedType((".jpg", ".jpeg"), ".jpg"),
    "image/png": AllowedType((".png",), ".png"),
    "image/webp": AllowedType((".webp",), ".webp"),
}


def sniff_mime(data: bytes) -> str | None:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


_SAFE_PUNCTUATION = frozenset("._- ()")
_UNDERSCORE_RUNS = re.compile(r"_+")


def _filename_char(ch: str) -> str:
    # Letters, combining marks (needed for Indic scripts) and digits are kept.
    if unicodedata.category(ch)[0] in "LMN" or ch in _SAFE_PUNCTUATION:
        return ch
    return "_"


def safe_filename(name: str, canonical_ext: str, allowed_exts: tuple[str, ...]) -> str:
    """Display-only name. Never used as a filesystem path."""
    name = unicodedata.normalize("NFC", name or "")
    name = name.replace("\\", "/").rsplit("/", 1)[-1]  # drop any path component
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")  # control chars
    name = _UNDERSCORE_RUNS.sub("_", "".join(_filename_char(ch) for ch in name)).strip(" .")
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    stem = stem.strip(" .") or "document"
    ext = f".{ext.lower()}" if ext else ""
    if ext not in allowed_exts:
        ext = canonical_ext
    return f"{stem[:120]}{ext}"


def validate_upload(filename: str | None, declared_mime: str | None, data: bytes, max_bytes: int) -> tuple[str, str]:
    """Return (safe_display_name, mime_type) or raise InvalidInput."""
    if not data:
        raise InvalidInput("The file is empty", code="empty_file")
    if len(data) > max_bytes:
        raise InvalidInput(f"File is larger than the {max_bytes // (1024 * 1024)} MB limit", code="file_too_large")
    declared = (declared_mime or "").split(";")[0].strip().lower()
    if declared not in ALLOWED_TYPES:
        raise InvalidInput("Only PDF, JPEG, PNG or WEBP files are accepted", code="unsupported_type")
    sniffed = sniff_mime(data)
    if sniffed != declared:
        raise InvalidInput("File content does not match its type", code="content_mismatch")
    allowed = ALLOWED_TYPES[declared]
    raw_name = (filename or "").lower()
    raw_ext = "." + raw_name.rsplit(".", 1)[-1] if "." in raw_name else ""
    if raw_ext and raw_ext not in allowed.extensions:
        raise InvalidInput("File extension is not allowed for this type", code="bad_extension")
    return safe_filename(filename or "", allowed.canonical_ext, allowed.extensions), declared


def upload_document(
    db: Session,
    storage: ObjectStorageProvider,
    *,
    patient: PatientProfile,
    actor: User,
    filename: str | None,
    declared_mime: str | None,
    data: bytes,
    document_type: DocumentType,
    source_language: LanguageCode | None,
    title: str | None,
    max_bytes: int,
) -> MedicalDocument:
    display_name, mime = validate_upload(filename, declared_mime, data, max_bytes)
    doc_id = uuid.uuid4()
    key = f"patients/{patient.id}/documents/{doc_id}{ALLOWED_TYPES[mime].canonical_ext}"
    reference = storage.put(key, data, mime)
    doc = MedicalDocument(
        id=doc_id,
        patient_id=patient.id,
        file_name=display_name,
        mime_type=mime,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        storage_reference=reference,
        document_type=document_type,
        title=(title or "").strip()[:200] or None,
        source_language=source_language,
        status=DocumentStatus.UPLOADED,
        uploaded_by_user_id=actor.id,
    )
    db.add(doc)
    audit.record(
        db, actor=actor, action="document.uploaded", resource_type="document", resource_id=doc_id,
        patient_id=patient.id, details={"document_type": document_type.value, "mime_type": mime},
    )
    try:
        db.commit()
    except Exception:
        storage.delete(reference)  # do not leave orphaned files behind
        raise
    return doc


def list_documents(db: Session, patient: PatientProfile) -> list[MedicalDocument]:
    return list(
        db.scalars(
            select(MedicalDocument)
            .where(MedicalDocument.patient_id == patient.id)
            .order_by(MedicalDocument.uploaded_at.desc())
        )
    )


def get_own_document(db: Session, patient: PatientProfile, document_id: uuid.UUID) -> MedicalDocument:
    doc = db.get(MedicalDocument, document_id)
    if doc is None or doc.patient_id != patient.id:
        raise NotFound("Document not found")
    return doc
