import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models import MedicalDocument
from app.providers.storage import get_storage
from app.services.document_service import safe_filename
from tests.conftest import EXE_BYTES, PDF_BYTES, PNG_BYTES, upload


def test_upload_pdf_and_download(client, make_patient, db):
    p = make_patient()
    r = upload(client, p, name="Lipid Profile.pdf")
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["status"] == "uploaded"
    assert doc["document_type"] == "lab_report"
    assert doc["file_name"] == "Lipid Profile.pdf"
    f = client.get(f"/api/v1/patients/me/documents/{doc['id']}/file", headers=p.h)
    assert f.status_code == 200
    assert f.content == PDF_BYTES
    assert f.headers["content-type"] == "application/pdf"
    assert f.headers["x-content-type-options"] == "nosniff"
    row = db.scalar(select(MedicalDocument))
    assert "Lipid" not in row.storage_reference  # user filename never used as storage key
    assert get_storage().exists(row.storage_reference)


def test_upload_png(client, make_patient):
    p = make_patient()
    r = upload(client, p, content=PNG_BYTES, name="scan.png", mime="image/png", document_type="scan")
    assert r.status_code == 201


@pytest.mark.parametrize(
    ("content", "name", "mime", "code"),
    [
        (EXE_BYTES, "setup.exe", "application/x-msdownload", "unsupported_type"),
        (EXE_BYTES, "report.pdf", "application/pdf", "content_mismatch"),
        (PDF_BYTES, "report.exe", "application/pdf", "bad_extension"),
        (PNG_BYTES, "image.pdf", "application/pdf", "content_mismatch"),
        (b"", "empty.pdf", "application/pdf", "empty_file"),
        (b"<html><script>alert(1)</script>", "x.html", "text/html", "unsupported_type"),
    ],
)
def test_upload_rejections(client, make_patient, content, name, mime, code):
    p = make_patient()
    r = upload(client, p, content=content, name=name, mime=mime)
    assert r.status_code == 422
    assert r.json()["code"] == code


def test_upload_too_large(client, make_patient):
    p = make_patient()
    big = b"%PDF-1.4\n" + b"0" * (get_settings().max_upload_bytes + 10)
    r = upload(client, p, content=big)
    assert r.status_code in (413, 422)


def test_invalid_document_type(client, make_patient):
    p = make_patient()
    r = upload(client, p, document_type="xray-of-doom")
    assert r.status_code == 422


def test_path_traversal_filename_is_neutralised(client, make_patient):
    p = make_patient()
    r = upload(client, p, name="../../etc/passwd.pdf")
    assert r.status_code == 201
    assert r.json()["file_name"] == "passwd.pdf"


def test_other_patient_cannot_read_document(client, make_patient):
    a = make_patient(email="a@example.com")
    b = make_patient(email="b@example.com")
    doc = upload(client, a).json()
    assert client.get(f"/api/v1/patients/me/documents/{doc['id']}", headers=b.h).status_code == 404
    assert client.get(f"/api/v1/patients/me/documents/{doc['id']}/file", headers=b.h).status_code == 404


def test_safe_filename_unit():
    exts = (".pdf",)
    assert safe_filename("..\\..\\windows\\evil.pdf", ".pdf", exts) == "evil.pdf"
    assert safe_filename("rep\x00ort.pdf", ".pdf", exts) == "report.pdf"
    assert safe_filename("", ".pdf", exts) == "document.pdf"
    assert safe_filename("noext", ".pdf", exts) == "noext.pdf"
    assert safe_filename("வரலாறு.pdf", ".pdf", exts) == "வரலாறு.pdf"  # unicode names preserved
