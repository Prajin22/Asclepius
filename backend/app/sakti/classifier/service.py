"""Product profiles and classification sessions (IP-SAKTI Phase 3).

    a user describes a product (their facts) → starts a session on the current
    tree version → answers one question at a time → the walk reaches a
    category (a proposal) or stops at "unknown" (information missing) → the
    user confirms or rejects the proposal, or revises answers, or restarts

Every result is written as an immutable outcome; revising an answer writes a
new one beside the old. Confirmation is explicit and names the outcome the
user saw. Nothing here infers an answer, fills a gap, or calls a model.

Ownership: a user sees and changes only their own products and sessions; any
other id is "not found", so nothing about another account is disclosed.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.models import (
    ClassificationAnswer,
    ClassificationOutcome,
    ClassificationSession,
    ClassifierReferenceLink,
    ProductProfile,
    ProvisionVersion,
    User,
)
from app.models.enums import (
    ClassificationStatus,
    CorpusReviewState,
    OutcomeKind,
    ReferenceStatus,
)
from app.sakti.classifier import engine, registry
from app.sakti.classifier.model import ReferenceSlot, Tree
from app.services import audit
from app.services.audit import RequestContext
from app.services.errors import Conflict, InvalidInput, InvalidTransition, NotFound

OPEN = (ClassificationStatus.INCOMPLETE, ClassificationStatus.REQUIRES_INFORMATION, ClassificationStatus.DETERMINED)
FINAL = (ClassificationStatus.USER_CONFIRMED, ClassificationStatus.USER_REJECTED, ClassificationStatus.SUPERSEDED)

#: The profile's user-provided fields, in the order a snapshot records them.
PROFILE_FIELDS = (
    "name", "intended_use", "dosage_form", "administration_route", "ingredients", "preparation_method",
    "classical_reference", "extract_description", "standardization_description", "markers", "notes",
    "text_language",
)


def _now() -> datetime:
    return datetime.now(UTC)


def _audit(db: Session, actor: User, action: str, resource: str, resource_id, ctx, **details: Any) -> None:
    audit.record(db, actor=actor, action=action, resource_type=resource, resource_id=resource_id,
                 details=details, ctx=ctx)


def _commit(db: Session) -> None:
    """Commit, turning a lost race on a versioned row into a plain conflict."""
    try:
        db.commit()
    except (StaleDataError, IntegrityError):
        db.rollback()
        raise Conflict("This changed at the same moment somewhere else. Reload and try again.",
                       code="classification_conflict") from None


# ---------------------------------------------------------------------------
# Product profiles
# ---------------------------------------------------------------------------


def list_products(db: Session, owner: User) -> list[ProductProfile]:
    return list(db.scalars(select(ProductProfile).where(ProductProfile.owner_user_id == owner.id)
                           .order_by(ProductProfile.created_at.desc())))


def get_own_product(db: Session, owner: User, product_id: uuid.UUID) -> ProductProfile:
    product = db.get(ProductProfile, product_id)
    if product is None or product.owner_user_id != owner.id:
        raise NotFound("Product not found")
    return product


def create_product(db: Session, owner: User, fields: dict[str, Any], ctx: RequestContext | None = None) -> ProductProfile:
    product = ProductProfile(owner_user_id=owner.id, **fields)
    db.add(product)
    db.flush()
    _audit(db, owner, "product.created", "product_profile", product.id, ctx,
           fields=sorted(k for k, v in fields.items() if v not in (None, "", [])))
    db.commit()
    return product


def update_product(db: Session, owner: User, product_id: uuid.UUID, changes: dict[str, Any],
                   ctx: RequestContext | None = None) -> ProductProfile:
    """Change what the user says about their product. Sessions already started keep their copy."""
    product = get_own_product(db, owner, product_id)
    changed = sorted(k for k, v in changes.items() if getattr(product, k) != v)
    for key in changed:
        setattr(product, key, changes[key])
    if changed:
        _audit(db, owner, "product.updated", "product_profile", product.id, ctx, fields=changed)
    _commit(db)
    return product


def snapshot(product: ProductProfile) -> dict[str, Any]:
    """The profile as it stands, JSON-safe, for a session to keep."""
    data: dict[str, Any] = {}
    for key in PROFILE_FIELDS:
        value = getattr(product, key)
        data[key] = value.value if hasattr(value, "value") else value
    return data


# ---------------------------------------------------------------------------
# The tree a session was walked under, and its reference slots
# ---------------------------------------------------------------------------


def tree_of(session: ClassificationSession) -> Tree:
    """The exact tree a session started under — refused if this build's copy differs."""
    try:
        tree = registry.get_tree(session.tree_version, session.classifier_id)
    except registry.UnknownTree as exc:
        raise Conflict(str(exc), code="classifier_tree_unavailable") from None
    if tree.fingerprint() != session.tree_fingerprint:
        raise Conflict("The classifier tree this session used has changed in this build",
                       code="classifier_tree_changed")
    return tree


@dataclass(frozen=True)
class ReferenceState:
    slot: ReferenceSlot
    status: ReferenceStatus
    link: ClassifierReferenceLink | None = None
    version: ProvisionVersion | None = None


def reference_states(db: Session, tree: Tree) -> dict[str, ReferenceState]:
    """Every slot of a tree, with its current status. No link means corpus_required."""
    links: dict[str, ClassifierReferenceLink] = {}
    for link in db.scalars(
        select(ClassifierReferenceLink)
        .where(ClassifierReferenceLink.classifier_id == tree.classifier_id,
               ClassifierReferenceLink.tree_version == tree.version)
        .order_by(ClassifierReferenceLink.created_at, ClassifierReferenceLink.id)
    ):
        links[link.slot_id] = link  # the latest link wins
    states: dict[str, ReferenceState] = {}
    for slot in tree.slots:
        link = links.get(slot.id)
        if link is None:
            states[slot.id] = ReferenceState(slot, ReferenceStatus.CORPUS_REQUIRED)
            continue
        version = db.get(ProvisionVersion, link.provision_version_id)
        verified = (version is not None and version.review_state == CorpusReviewState.APPROVED
                    and version.lane == slot.lane)
        states[slot.id] = ReferenceState(
            slot, ReferenceStatus.VERIFIED if verified else ReferenceStatus.UNVERIFIED, link, version
        )
    return states


def link_reference(db: Session, curator: User, version: int, slot_id: str, provision_version_id: uuid.UUID,
                   ctx: RequestContext | None = None) -> ClassifierReferenceLink:
    """Point a reference slot at approved corpus text. Only approved text, only the slot's lane."""
    try:
        tree = registry.get_tree(version)
    except registry.UnknownTree:
        raise NotFound("Classifier tree version not found") from None
    slot = tree.slots_by_id.get(slot_id)
    if slot is None:
        raise NotFound("Reference slot not found")
    provision_version = db.get(ProvisionVersion, provision_version_id)
    if provision_version is None:
        raise NotFound("Provision version not found")
    if provision_version.review_state != CorpusReviewState.APPROVED:
        raise Conflict("Only approved corpus text can support the classifier", code="provision_not_approved")
    if provision_version.lane != slot.lane:
        raise InvalidInput("That provision belongs to the other lane", code="lane_mismatch")
    link = ClassifierReferenceLink(
        classifier_id=tree.classifier_id, tree_version=tree.version, slot_id=slot.id,
        provision_version_id=provision_version.id, lane=provision_version.lane, linked_by_user_id=curator.id,
    )
    db.add(link)
    db.flush()
    _audit(db, curator, "classification.reference_linked", "classifier_reference", link.id, ctx,
           slot_id=slot.id, tree_version=tree.version, provision_version_id=str(provision_version.id))
    db.commit()
    return link


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def get_own_session(db: Session, owner: User, session_id: uuid.UUID) -> ClassificationSession:
    session = db.get(ClassificationSession, session_id)
    if session is None or session.owner_user_id != owner.id:
        raise NotFound("Classification not found")
    return session


def sessions_for_product(db: Session, owner: User, product_id: uuid.UUID) -> list[ClassificationSession]:
    get_own_product(db, owner, product_id)
    return list(db.scalars(select(ClassificationSession).where(ClassificationSession.product_id == product_id)
                           .order_by(ClassificationSession.created_at.desc())))


def current_answer_rows(db: Session, session_id: uuid.UUID) -> list[ClassificationAnswer]:
    return list(db.scalars(select(ClassificationAnswer).where(
        ClassificationAnswer.session_id == session_id, ClassificationAnswer.superseded_at.is_(None))))


def answer_history(db: Session, session_id: uuid.UUID) -> list[ClassificationAnswer]:
    return list(db.scalars(select(ClassificationAnswer).where(ClassificationAnswer.session_id == session_id)
                           .order_by(ClassificationAnswer.answered_at, ClassificationAnswer.id)))


def outcomes_of(db: Session, session_id: uuid.UUID) -> list[ClassificationOutcome]:
    return list(db.scalars(select(ClassificationOutcome).where(ClassificationOutcome.session_id == session_id)
                           .order_by(ClassificationOutcome.sequence)))


def latest_outcome(db: Session, session_id: uuid.UUID) -> ClassificationOutcome | None:
    return db.scalar(select(ClassificationOutcome).where(ClassificationOutcome.session_id == session_id)
                     .order_by(ClassificationOutcome.sequence.desc()).limit(1))


def current_walk(db: Session, session: ClassificationSession) -> tuple[Tree, engine.Walk]:
    tree = tree_of(session)
    answers = {row.node_id: row.choice for row in current_answer_rows(db, session.id)}
    return tree, engine.walk(tree, answers)


def _new_session(db: Session, owner: User, product: ProductProfile, restarted_from: uuid.UUID | None,
                 ctx: RequestContext | None) -> ClassificationSession:
    tree = registry.current_tree()
    session = ClassificationSession(
        product_id=product.id, owner_user_id=owner.id, classifier_id=tree.classifier_id, tree_version=tree.version,
        tree_fingerprint=tree.fingerprint(), status=ClassificationStatus.INCOMPLETE, current_node_id=tree.start,
        product_revision=product.revision, product_snapshot=snapshot(product), restarted_from_id=restarted_from,
    )
    db.add(session)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Conflict("This product already has a classification in progress", code="classification_open") from None
    _audit(db, owner, "classification.session_created", "classification", session.id, ctx,
           product_id=str(product.id), classifier_id=tree.classifier_id, tree_version=tree.version,
           restarted_from=str(restarted_from) if restarted_from else None)
    _audit(db, owner, "classification.question_presented", "classification", session.id, ctx,
           node_id=tree.start, tree_version=tree.version)
    return session


def start_session(db: Session, owner: User, product_id: uuid.UUID, ctx: RequestContext | None = None) -> ClassificationSession:
    product = get_own_product(db, owner, product_id)
    session = _new_session(db, owner, product, None, ctx)
    db.commit()
    return session


def _refuse_final(db: Session, owner: User, session: ClassificationSession, attempted: str, ctx) -> None:
    if session.status not in FINAL:
        return
    _audit(db, owner, "classification.change_refused", "classification", session.id, ctx,
           attempted=attempted, status=session.status.value, tree_version=session.tree_version)
    db.commit()
    raise Conflict("This classification is final. Start again to classify the product afresh.",
                   code="classification_final")


def _record_outcome(db: Session, owner: User, session: ClassificationSession, tree: Tree, walk: engine.Walk,
                    ctx) -> ClassificationOutcome:
    states = reference_states(db, tree)
    refs = [
        {"slot_id": slot_id, "status": states[slot_id].status.value,
         "provision_version_id": str(states[slot_id].link.provision_version_id) if states[slot_id].link else None}
        for slot_id in walk.references(tree)
    ]
    sequence = (db.scalar(select(func.max(ClassificationOutcome.sequence))
                          .where(ClassificationOutcome.session_id == session.id)) or 0) + 1
    determined = walk.state == "determined"
    outcome = ClassificationOutcome(
        session_id=session.id, sequence=sequence,
        kind=OutcomeKind.DETERMINED if determined else OutcomeKind.REQUIRES_INFORMATION,
        category=walk.category if determined else None, stop_node_id=None if determined else walk.node_id,
        path=[[s.node_id, s.choice] for s in walk.path], answers_sha256=engine.answers_sha256(walk.path),
        tree_version=tree.version, tree_fingerprint=tree.fingerprint(), references=refs,
    )
    db.add(outcome)
    db.flush()
    unverified = [r["slot_id"] for r in refs if r["status"] != ReferenceStatus.VERIFIED.value]
    if determined:
        _audit(db, owner, "classification.determined", "classification", session.id, ctx,
               outcome_id=str(outcome.id), category=walk.category.value, answers_sha256=outcome.answers_sha256,
               tree_version=tree.version, references_unverified=unverified)
    else:
        _audit(db, owner, "classification.unknown_encountered", "classification", session.id, ctx,
               outcome_id=str(outcome.id), node_id=walk.node_id, tree_version=tree.version)
    return outcome


def answer(db: Session, owner: User, session_id: uuid.UUID, node_id: str, choice: str,
           ctx: RequestContext | None = None) -> ClassificationSession:
    """Record an answer, or revise one already given, and walk the tree again."""
    session = get_own_session(db, owner, session_id)
    _refuse_final(db, owner, session, "answer", ctx)
    tree, walk = current_walk(db, session)
    node = tree.by_id.get(node_id)
    answerable = {s.node_id for s in walk.path} | ({walk.node_id} if walk.state == "ask" else set())
    if node is None or node_id not in answerable:
        raise Conflict("That question does not apply at this point", code="question_not_applicable")
    if choice not in node.choice_ids:
        raise InvalidInput("That is not one of the question's choices", code="invalid_choice")

    rows = {row.node_id: row for row in current_answer_rows(db, session.id)}
    previous = rows.get(node_id)
    if previous is not None and previous.choice == choice:
        return session  # the same answer again: nothing changes

    now = _now()
    retired: list[str] = []
    if previous is not None:
        order = [s.node_id for s in walk.path]
        retired = order[order.index(node_id):]
        for retired_id in retired:
            rows[retired_id].superseded_at = now
        db.flush()
    db.add(ClassificationAnswer(session_id=session.id, node_id=node_id, choice=choice,
                                answered_by_user_id=owner.id, answered_at=now))
    db.flush()
    if previous is not None:
        _audit(db, owner, "classification.answer_changed", "classification", session.id, ctx,
               node_id=node_id, previous=previous.choice, choice=choice, retired=retired[1:],
               tree_version=tree.version)
    else:
        _audit(db, owner, "classification.answer_recorded", "classification", session.id, ctx,
               node_id=node_id, choice=choice, tree_version=tree.version)

    _, walk = current_walk(db, session)
    if walk.state == "ask":
        session.status, session.current_node_id = ClassificationStatus.INCOMPLETE, walk.node_id
        _audit(db, owner, "classification.question_presented", "classification", session.id, ctx,
               node_id=walk.node_id, tree_version=tree.version)
    elif walk.state == "stopped":
        session.status, session.current_node_id = ClassificationStatus.REQUIRES_INFORMATION, walk.node_id
        _record_outcome(db, owner, session, tree, walk, ctx)
    else:
        session.status, session.current_node_id = ClassificationStatus.DETERMINED, None
        _record_outcome(db, owner, session, tree, walk, ctx)
    _commit(db)
    return session


def _decide(db: Session, owner: User, session_id: uuid.UUID, outcome_id: uuid.UUID, target: ClassificationStatus,
            reason: str | None, ctx) -> ClassificationSession:
    session = get_own_session(db, owner, session_id)
    action = "confirm" if target == ClassificationStatus.USER_CONFIRMED else "reject"
    _refuse_final(db, owner, session, action, ctx)
    if session.status != ClassificationStatus.DETERMINED:
        raise InvalidTransition("Only a determined classification can be confirmed or rejected",
                                code="classification_not_determined")
    outcome = latest_outcome(db, session.id)
    if outcome is None or outcome.id != outcome_id or outcome.kind != OutcomeKind.DETERMINED:
        raise Conflict("The classification shown is not the current one. Reload and look again.",
                       code="outcome_changed")
    session.status, session.decided_at, session.decided_by_user_id = target, _now(), owner.id
    session.decided_outcome_id, session.rejection_reason = outcome.id, reason
    _audit(db, owner, f"classification.{'confirmed' if action == 'confirm' else 'rejected'}", "classification",
           session.id, ctx, outcome_id=str(outcome.id), category=outcome.category.value,
           tree_version=session.tree_version)
    _commit(db)
    return session


def confirm(db: Session, owner: User, session_id: uuid.UUID, outcome_id: uuid.UUID,
            ctx: RequestContext | None = None) -> ClassificationSession:
    """The user accepts the proposed category as their product's classification."""
    return _decide(db, owner, session_id, outcome_id, ClassificationStatus.USER_CONFIRMED, None, ctx)


def reject(db: Session, owner: User, session_id: uuid.UUID, outcome_id: uuid.UUID, reason: str | None,
           ctx: RequestContext | None = None) -> ClassificationSession:
    """The user does not accept it. No other category is put in its place."""
    return _decide(db, owner, session_id, outcome_id, ClassificationStatus.USER_REJECTED, reason, ctx)


def restart(db: Session, owner: User, session_id: uuid.UUID, ctx: RequestContext | None = None) -> ClassificationSession:
    """A fresh session for the same product, on the current tree and the current profile.

    The old session is kept exactly as it was; if it was still open it is marked
    superseded so it can no longer be confirmed.
    """
    old = get_own_session(db, owner, session_id)
    product = get_own_product(db, owner, old.product_id)
    previous_status = old.status
    if old.status in OPEN:
        old.status = ClassificationStatus.SUPERSEDED
        try:
            db.flush()
        except StaleDataError:
            db.rollback()
            raise Conflict("This changed at the same moment somewhere else. Reload and try again.",
                           code="classification_conflict") from None
    new = _new_session(db, owner, product, old.id, ctx)
    _audit(db, owner, "classification.restarted", "classification", old.id, ctx,
           new_session_id=str(new.id), tree_version=new.tree_version, previous_status=previous_status.value)
    _commit(db)
    return new


def confirmed_classification(db: Session, product: ProductProfile) -> tuple[ClassificationSession, ClassificationOutcome] | None:
    """The product's most recent confirmed classification, with the outcome it confirmed."""
    session = db.scalar(select(ClassificationSession).where(
        ClassificationSession.product_id == product.id,
        ClassificationSession.status == ClassificationStatus.USER_CONFIRMED,
    ).order_by(ClassificationSession.decided_at.desc()).limit(1))
    if session is None or session.decided_outcome_id is None:
        return None
    outcome = db.get(ClassificationOutcome, session.decided_outcome_id)
    return (session, outcome) if outcome is not None else None
