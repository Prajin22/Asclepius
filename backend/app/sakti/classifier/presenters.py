"""Classifier records → API shapes. References show stored, approved metadata only — never quoted text."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ClassificationOutcome, ClassificationSession, CorpusDocument, ProductProfile
from app.models.enums import OutcomeKind, ReferenceStatus
from app.sakti.classifier import engine, registry, service
from app.sakti.classifier.model import Tree
from app.schemas.classification import (
    AnswerOut,
    ChoiceOut,
    ConfirmedClassification,
    NodeOut,
    OutcomeOut,
    OutcomeReference,
    ProductOut,
    ProvisionPointer,
    SessionOut,
    SessionSummary,
    SlotOut,
    StepOut,
    TreeOut,
)


def product_out(db: Session, product: ProductProfile) -> ProductOut:
    confirmed = service.confirmed_classification(db, product)
    open_id = db.scalar(select(ClassificationSession.id).where(
        ClassificationSession.product_id == product.id, ClassificationSession.status.in_(service.OPEN)))
    out = ProductOut.model_validate(product, from_attributes=True)
    if confirmed is not None:
        session, outcome = confirmed
        out.confirmed_classification = ConfirmedClassification(
            session_id=session.id, outcome_id=outcome.id, category=outcome.category,
            tree_version=session.tree_version, decided_at=session.decided_at,
        )
    out.open_session_id = open_id
    return out


def slot_out(db: Session, state: service.ReferenceState) -> SlotOut:
    pointer = None
    version = state.version
    if state.status == ReferenceStatus.VERIFIED and version is not None:
        provision = version.provision
        source = db.get(CorpusDocument, version.document_id)
        pointer = ProvisionPointer(
            provision_version_id=version.id, locator=provision.locator, version_number=version.version_number,
            instrument_title=provision.instrument.title, source_title=source.title,
            source_authority=source.source_authority,
        )
    return SlotOut(id=state.slot.id, lane=state.slot.lane, describes_key=state.slot.describes_key,
                   status=state.status, provision=pointer)


def tree_out(db: Session, tree: Tree) -> TreeOut:
    states = service.reference_states(db, tree)
    categories = []
    for node in tree.nodes:
        for _, nxt in node.transitions:
            if nxt.category is not None and nxt.category not in categories:
                categories.append(nxt.category)
    return TreeOut(
        classifier_id=tree.classifier_id, version=tree.version, fingerprint=tree.fingerprint(),
        current=tree.version == registry.CURRENT_VERSION, status=tree.status, legal_review=tree.legal_review,
        start=tree.start,
        nodes=[
            NodeOut(id=n.id, question_key=n.question_key, help_key=n.help_key, missing_key=n.missing_key,
                    why_key=n.why_key, choices=[ChoiceOut(id=c.id, label_key=c.label_key) for c in n.choices],
                    context_fields=list(n.context_fields), references=list(n.references))
            for n in tree.nodes
        ],
        categories=categories,
        slots=[slot_out(db, states[s.id]) for s in tree.slots],
    )


def outcome_out(outcome: ClassificationOutcome) -> OutcomeOut:
    return OutcomeOut(
        id=outcome.id, sequence=outcome.sequence, kind=outcome.kind, category=outcome.category,
        stop_node_id=outcome.stop_node_id, path=[StepOut(node_id=n, choice=c) for n, c in outcome.path],
        answers_sha256=outcome.answers_sha256, tree_version=outcome.tree_version,
        references=[OutcomeReference(**ref) for ref in outcome.references], created_at=outcome.created_at,
    )


def _category(db: Session, session: ClassificationSession):
    """The category the session's current answers lead to, if they lead to one that was recorded."""
    outcome = service.latest_outcome(db, session.id)
    if outcome is None or outcome.kind != OutcomeKind.DETERMINED:
        return None
    _, walk = service.current_walk(db, session)
    if walk.state != "determined" or engine.answers_sha256(walk.path) != outcome.answers_sha256:
        return None  # an answer was revised since; that category no longer stands
    return outcome.category


def session_summary(db: Session, session: ClassificationSession) -> SessionSummary:
    return SessionSummary(
        id=session.id, product_id=session.product_id, status=session.status, tree_version=session.tree_version,
        category=_category(db, session), created_at=session.created_at, decided_at=session.decided_at,
        restarted_from_id=session.restarted_from_id,
    )


def session_out(db: Session, session: ClassificationSession) -> SessionOut:
    tree, walk = service.current_walk(db, session)
    outcomes = service.outcomes_of(db, session.id)
    latest = outcomes[-1] if outcomes else None
    states = service.reference_states(db, tree)
    slots = [r["slot_id"] for r in latest.references] if latest else []
    product = db.get(ProductProfile, session.product_id)
    return SessionOut(
        **session_summary(db, session).model_dump(),
        product_name=product.name, classifier_id=session.classifier_id, tree_fingerprint=session.tree_fingerprint,
        current_node_id=session.current_node_id, path=[StepOut(node_id=s.node_id, choice=s.choice) for s in walk.path],
        latest_outcome=outcome_out(latest) if latest else None, outcomes=[outcome_out(o) for o in outcomes],
        answer_history=[AnswerOut.model_validate(a, from_attributes=True)
                        for a in service.answer_history(db, session.id)],
        references=[slot_out(db, states[slot_id]) for slot_id in slots if slot_id in states],
        product_revision=session.product_revision, product_snapshot=session.product_snapshot,
        decided_outcome_id=session.decided_outcome_id, rejection_reason=session.rejection_reason,
        updated_at=session.updated_at,
    )
