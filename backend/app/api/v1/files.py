from urllib.parse import quote

from fastapi import HTTPException, Response

from app.models import MedicalDocument
from app.providers.storage import ObjectNotFound, get_storage


def page_image_response(png: bytes) -> Response:
    """A rendered page of an original document. Same protections as the file itself."""
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cache-Control": "private, no-store",
        },
    )


def document_file_response(doc: MedicalDocument) -> Response:
    try:
        data = get_storage().get(doc.storage_reference)
    except ObjectNotFound:
        raise HTTPException(404, detail="File is missing from storage") from None
    return Response(
        content=data,
        media_type=doc.mime_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(doc.file_name)}",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cache-Control": "private, no-store",
        },
    )
