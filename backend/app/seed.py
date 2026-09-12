"""Synthetic demo data. NO REAL PATIENT DATA.

    python -m app.seed            # seed if empty
    python -m app.seed --reset    # wipe ALL data, then seed

Every person, clinic, registration number and document here is fictional.
"""

import argparse
import sys
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.languages import LanguageCode as L
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal
from app.models import (
    Consultation,
    ConsultationMessage,
    ConsultationShare,
    MedicalDocument,
    MedicalRecord,
    PatientProfile,
    Prescription,
    PrescriptionItem,
    User,
)
from app.models.enums import (
    ConsultationStatus,
    DocumentType,
    RecordSource,
    RecordStatus,
    RecordType,
    Sex,
    ShareItemType,
    UserRole,
)
from app import synthetic_documents
from app.providers.storage import get_storage
from app.schemas.auth import PatientRegisterRequest
from app.schemas.doctor import DoctorCreate
from app.services import auth_service, document_service

ADMIN = ("admin@carebridge.demo", "Admin@2026")
PATIENT = ("arun.kumar@carebridge.demo", "Patient@2026")
DOCTOR_PASSWORD = "Doctor@2026"

SYNTHETIC_BANNER = "SYNTHETIC DEMO DOCUMENT - NOT A REAL MEDICAL RECORD"

DOCTORS = [
    dict(key="meera", email="meera.sharma@carebridge.demo", name="Dr. Meera Sharma", specialization="General Medicine",
         qualification="MBBS, MD (General Medicine)", registration_identifier="DEMO-REG-GM-0001",
         clinic_name="Sunrise Family Clinic (demo)", clinic_address="12 Demo Street, Adyar, Chennai 600020",
         phone="+91 44 0000 0101", languages=[L.EN, L.HI, L.TA]),
    dict(key="rajesh", email="rajesh.iyer@carebridge.demo", name="Dr. Rajesh Iyer", specialization="Cardiology",
         qualification="MBBS, MD, DM (Cardiology)", registration_identifier="DEMO-REG-CA-0002",
         clinic_name="Heartline Cardiac Centre (demo)", clinic_address="45 Sample Road, T. Nagar, Chennai 600017",
         phone="+91 44 0000 0202", languages=[L.EN, L.TA]),
    dict(key="fatima", email="fatima.khan@carebridge.demo", name="Dr. Fatima Khan", specialization="Dermatology",
         qualification="MBBS, MD (Dermatology)", registration_identifier="DEMO-REG-DE-0003",
         clinic_name="Clearskin Clinic (demo)", clinic_address="8 Example Lane, Anna Nagar, Chennai 600040",
         phone="+91 44 0000 0303", languages=[L.EN, L.HI]),
    dict(key="anitha", email="anitha.rao@carebridge.demo", name="Dr. Anitha Rao", specialization="Endocrinology",
         qualification="MBBS, MD, DM (Endocrinology)", registration_identifier="DEMO-REG-EN-0004",
         clinic_name="Balance Endocrine Care (demo)", clinic_address="3 Placeholder Avenue, Velachery, Chennai 600042",
         phone="+91 44 0000 0404", languages=[L.EN, L.KN, L.TA]),
]


def make_pdf(lines: list[str]) -> bytes:
    """Tiny valid one-page PDF (Helvetica, ASCII) — enough for demo documents."""

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    ops = ["BT", "/F1 12 Tf", "16 TL", "56 780 Td"] + [f"({esc(line)}) Tj T*" for line in lines] + ["ET"]
    stream = "\n".join(ops).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


LIPID_REPORT = [
    SYNTHETIC_BANNER, "", "Demo Diagnostics Laboratory (fictional)", "Lipid Profile - Fasting", "",
    "Patient: Arun Kumar (synthetic)      Age/Sex: 46 / M", "Sample date: 02 March 2026", "",
    "Total cholesterol ........ 212 mg/dL   (ref < 200)", "LDL cholesterol .......... 138 mg/dL   (ref < 100)",
    "HDL cholesterol ..........  42 mg/dL   (ref > 40)", "Triglycerides ............ 160 mg/dL   (ref < 150)", "",
    "Generated for software demonstration only.",
]
OLD_PRESCRIPTION = [
    SYNTHETIC_BANNER, "", "Community Health Clinic (fictional)", "Outpatient prescription - 14 June 2024", "",
    "Patient: Arun Kumar (synthetic)", "Rx: Amlodipine 5 mg - 1 tablet once daily in the morning", "",
    "Generated for software demonstration only.",
]
BP_LOG = [
    SYNTHETIC_BANNER, "", "Home blood pressure log (patient-recorded)", "Arun Kumar (synthetic)", "",
    "Mon  morning 146/92   evening 140/88", "Tue  morning 150/94   evening 142/90",
    "Wed  morning 148/93   evening 139/87", "Thu  morning 152/96   evening 144/90", "",
    "Generated for software demonstration only.",
]
ECG_NOTE = [
    SYNTHETIC_BANNER, "", "Demo Heart Clinic (fictional)", "Resting ECG - summary sheet", "",
    "Patient: Arun Kumar (synthetic)", "Rhythm: sinus. Rate: 78 bpm.", "Interpretation left blank for demo.", "",
    "Generated for software demonstration only.",
]


def reset(db: Session) -> None:
    storage = get_storage()
    for ref in db.scalars(select(MedicalDocument.storage_reference)):
        storage.delete(ref)
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()


def _backdate(obj, when: datetime, *fields: str) -> None:
    for f in fields or ("created_at", "updated_at"):
        setattr(obj, f, when)


def seed(db: Session) -> None:
    if auth_service.get_user_by_email(db, PATIENT[0]):
        print("Demo data already present. Use --reset to recreate it.")
        return
    now = datetime.now(UTC)

    admin = User(role=UserRole.ADMIN, email=ADMIN[0], password_hash=hash_password(ADMIN[1]))
    db.add(admin)
    db.commit()

    doctors = {}
    for spec in DOCTORS:
        key = spec.pop("key")
        doctors[key] = auth_service.create_doctor(db, DoctorCreate(password=DOCTOR_PASSWORD, **spec), actor=admin)
        spec["key"] = key

    patient_user = auth_service.register_patient(
        db, PatientRegisterRequest(email=PATIENT[0], password=PATIENT[1], display_name="Arun Kumar",
                                   preferred_language=L.TA)
    )
    patient = db.scalar(select(PatientProfile).where(PatientProfile.user_id == patient_user.id))
    patient.date_of_birth = date(1980, 3, 15)
    patient.sex = Sex.MALE
    patient.phone = "+91 90000 00001"
    patient.emergency_contact_name = "Lakshmi Kumar (spouse)"
    patient.emergency_contact_phone = "+91 90000 00002"
    patient.emergency_notes = "Blood group B+ (self-reported). Allergic to penicillin."

    def record(type_, title, content, lang, *, source=RecordSource.PATIENT, status=RecordStatus.ACTIVE,
               days_ago=200, by=None):
        r = MedicalRecord(patient_id=patient.id, type=type_, title=title, content=content, source=source,
                          source_language=lang, status=status, recorded_by_user_id=by or patient_user.id)
        _backdate(r, now - timedelta(days=days_ago))
        db.add(r)
        return r

    hypertension = record(
        RecordType.CONDITION, "Hypertension (high blood pressure)",
        "சுமார் 5 வருடங்களாக இரத்த அழுத்தம் அதிகமாக உள்ளது. தினமும் காலையில் மாத்திரை எடுத்துக்கொள்கிறேன்.", L.TA,
    )
    record(RecordType.ALLERGY, "Penicillin", "Skin rash and itching after an injection in 2015.", L.EN)
    record(RecordType.MEDICATION, "Amlodipine 5 mg", "One tablet every morning.", L.EN)
    record(RecordType.CONDITION, "Typhoid fever", "Treated in 2019. Fully recovered.", L.EN,
           status=RecordStatus.RESOLVED)
    record(RecordType.HISTORY_NOTE, "Family history", "Father had type 2 diabetes. Mother has high blood pressure.",
           L.EN)
    old_problem = record(
        RecordType.CURRENT_PROBLEM, None,
        "ஒரு வாரமாக காலையில் எழுந்தவுடன் தலைவலி. மருந்துக் கடையில் BP பார்த்தபோது 150/95 என்று சொன்னார்கள்.",
        L.TA, status=RecordStatus.RESOLVED, days_ago=152,
    )
    db.commit()

    storage = get_storage()
    max_bytes = get_settings().max_upload_bytes
    # Stored, not read: reading a document needs the patient's AI consent (demo step).
    for data, name, dtype, title, days in [
        (make_pdf(LIPID_REPORT), "lipid-profile-mar-2026.pdf", DocumentType.LAB_REPORT, "Lipid profile", 194),
        (make_pdf(OLD_PRESCRIPTION), "clinic-prescription-2024.pdf", DocumentType.PRESCRIPTION,
         "Old clinic prescription", 190),
        (synthetic_documents.text_pdf(synthetic_documents.DISCHARGE_SUMMARY), "discharge-summary.pdf",
         DocumentType.DISCHARGE_SUMMARY, "Discharge summary", 60),
        (synthetic_documents.scanned_pdf(synthetic_documents.SCANNED_LAB), "scanned-blood-count.pdf",
         DocumentType.LAB_REPORT, "Blood count (scanned)", 20),
    ]:
        doc = document_service.upload_document(
            db, storage, patient=patient, actor=patient_user, filename=name, declared_mime="application/pdf",
            data=data, document_type=dtype, source_language=L.EN, title=title, max_bytes=max_bytes,
        )
        doc.uploaded_at = now - timedelta(days=days)
    db.commit()

    # One realistic completed consultation with a cardiologist, ~5 months ago.
    rajesh = doctors["rajesh"]
    t0 = now - timedelta(days=150)
    c = Consultation(
        patient_id=patient.id, doctor_id=rajesh.id, status=ConsultationStatus.COMPLETED,
        request_message="காலை நேர தலைவலி மற்றும் BP அதிகம் பற்றி ஆலோசனை வேண்டும்.", request_language=L.TA,
        patient_shared_context={
            "version": 1, "decided_at": t0.isoformat(),
            "categories": {
                "current_problem": {"shared": True, "item_ids": [str(old_problem.id)]},
                "medical_history": {"shared": True, "item_ids": [str(hypertension.id)]},
                "documents": {"shared": False, "item_ids": []},
                "previous_consultations": {"shared": False, "item_ids": []},
                "previous_prescriptions": {"shared": False, "item_ids": []},
            },
        },
        doctor_assessment=(
            "Home BP readings average about 148/94 on amlodipine 5 mg. No red-flag symptoms reported "
            "(no chest pain, breathlessness or weakness). Continue current medication. Reduce salt intake, "
            "walk 30 minutes daily. Keep a home BP log and review in 3 months."
        ),
        accepted_at=t0 + timedelta(hours=2), started_at=t0 + timedelta(hours=2),
        completed_at=t0 + timedelta(days=1),
    )
    _backdate(c, t0)
    c.shares = [
        ConsultationShare(item_type=ShareItemType.MEDICAL_RECORD, item_id=old_problem.id, granted_at=t0),
        ConsultationShare(item_type=ShareItemType.MEDICAL_RECORD, item_id=hypertension.id, granted_at=t0),
    ]
    c.messages = [
        ConsultationMessage(sender_user_id=patient_user.id, sender_role=UserRole.PATIENT, language=L.TA,
                            body="வணக்கம் டாக்டர். கடந்த வாரம் முழுவதும் காலையில் தலைவலி இருந்தது.",
                            created_at=t0 + timedelta(hours=2, minutes=5)),
        ConsultationMessage(sender_user_id=rajesh.user_id, sender_role=UserRole.DOCTOR, language=L.EN,
                            body="Thank you. Please check your BP at home twice a day for the next week and "
                                 "share the readings here.",
                            created_at=t0 + timedelta(hours=2, minutes=20)),
        ConsultationMessage(sender_user_id=patient_user.id, sender_role=UserRole.PATIENT, language=L.TA,
                            body="சரி டாக்டர், அனுப்புகிறேன்.", created_at=t0 + timedelta(hours=2, minutes=24)),
    ]
    db.add(c)
    db.flush()
    rx = Prescription(
        consultation_id=c.id, doctor_id=rajesh.id, patient_id=patient.id,
        instructions="Check BP at home twice a week and bring the log to the next visit. Reduce added salt.",
        created_at=t0 + timedelta(days=1),
        items=[PrescriptionItem(position=1, medication="Amlodipine 5 mg", dosage="1 tablet",
                                frequency="Once daily, morning", duration="90 days", instructions="After breakfast")],
    )
    db.add(rx)
    # A doctor-provided entry from that consultation, to show attribution in the UI.
    record(RecordType.CONDITION, "Stage 1 hypertension",
           "Recorded by Dr. Rajesh Iyer during consultation: home BP average ~148/94 on treatment.",
           L.EN, source=RecordSource.DOCTOR, days_ago=149, by=rajesh.user_id)
    db.commit()

    print("Seeded synthetic demo data.\n")
    print(f"  Patient  {PATIENT[0]:<34} {PATIENT[1]}")
    for spec in DOCTORS:
        print(f"  Doctor   {spec['email']:<34} {DOCTOR_PASSWORD}")
    print(f"  Admin    {ADMIN[0]:<34} {ADMIN[1]}")


def write_samples(target: str) -> None:
    from pathlib import Path

    out = Path(target)
    out.mkdir(parents=True, exist_ok=True)
    (out / "synthetic-home-bp-log.pdf").write_bytes(make_pdf(BP_LOG))
    (out / "synthetic-ecg-summary.pdf").write_bytes(make_pdf(ECG_NOTE))
    # Phase 3: text-layer, scanned (OCR), photo (OCR) and prompt-injection samples.
    for name, (data, _mime) in synthetic_documents.all_samples().items():
        (out / name).write_bytes(data)
    print(f"Wrote sample upload documents to {out}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="delete ALL data before seeding")
    parser.add_argument("--write-samples", metavar="DIR", help="write sample PDFs for the upload demo and exit")
    args = parser.parse_args(argv)
    if args.write_samples:
        write_samples(args.write_samples)
        return 0
    if args.reset and get_settings().app_env not in ("development", "test"):
        print("Refusing --reset outside development/test.", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        if args.reset:
            reset(db)
        seed(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
