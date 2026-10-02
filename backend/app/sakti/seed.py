"""Synthetic demo accounts for IP-SAKTI Sahayak, one per role.

Accounts only. No product profiles, no questions, no answers, no source
documents and no legal text of any kind: nothing in Phase 1 can use them, and
legal text must come from official sources through the curator workflow, never
from a seed script.

Run through `python -m app.seed` with PRODUCT=ip_sakti.
"""

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User
from app.models.enums import UserRole
from app.services import auth_service

#: Not real people. Shown on the sign-in page when demo accounts are enabled.
DEMO_ACCOUNTS: tuple[tuple[UserRole, str, str], ...] = (
    (UserRole.USER, "user@asclepius.demo", "User@2026"),
    (UserRole.FACILITATOR, "facilitator@asclepius.demo", "Facilitator@2026"),
    (UserRole.CURATOR, "curator@asclepius.demo", "Curator@2026"),
    (UserRole.ADMIN, "admin@asclepius.demo", "Admin@2026"),
)


def seed(db: Session) -> None:
    if auth_service.get_user_by_email(db, DEMO_ACCOUNTS[0][1]):
        print("Asclepius demo accounts (PRODUCT=ip_sakti) already present. Use --reset to recreate them.")
        return
    for role, email, password in DEMO_ACCOUNTS:
        db.add(User(role=role, email=email, password_hash=hash_password(password)))
    db.commit()

    print("\nAsclepius demo accounts (PRODUCT=ip_sakti, synthetic):")
    for role, email, password in DEMO_ACCOUNTS:
        print(f"  {role.value:<12} {email:<28} {password}")
    print("No legal content is seeded. Answers, classification and the source library are not available yet.\n")
