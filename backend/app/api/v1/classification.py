"""The formulation classifier (IP-SAKTI Phase 3). Mounted only when PRODUCT=ip_sakti.

Sessions belong to the user who started them; anyone else's is "not found".
Every IP-SAKTI role may read the tree itself — it is configuration, not
anyone's data — and only a curator may link a reference slot to approved
corpus text. Nothing here answers a legal question.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import DB, Ctx, require_roles
from app.models import User
from app.models.enums import UserRole
from app.sakti.classifier import presenters, registry, service
from app.schemas.classification import (
    AnswerIn,
    ConfirmIn,
    ReferenceLinkIn,
    RejectIn,
    SessionOut,
    SlotOut,
    StartSession,
    TreeOut,
)
from app.services.errors import NotFound

router = APIRouter(prefix="/classifications", tags=["classification"])
tree_router = APIRouter(prefix="/classification-tree", tags=["classification"])

Owner = Annotated[User, Depends(require_roles(UserRole.USER))]
Curator = Annotated[User, Depends(require_roles(UserRole.CURATOR))]
AnyRole = Annotated[
    User, Depends(require_roles(UserRole.USER, UserRole.FACILITATOR, UserRole.CURATOR, UserRole.ADMIN))
]


# ---------- sessions ----------


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def start(data: StartSession, owner: Owner, db: DB, ctx: Ctx) -> SessionOut:
    """Start classifying one of your products on the current tree version."""
    return presenters.session_out(db, service.start_session(db, owner, data.product_id, ctx))


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: uuid.UUID, owner: Owner, db: DB) -> SessionOut:
    return presenters.session_out(db, service.get_own_session(db, owner, session_id))


@router.post("/{session_id}/responses", response_model=SessionOut)
def respond(session_id: uuid.UUID, data: AnswerIn, owner: Owner, db: DB, ctx: Ctx) -> SessionOut:
    """Answer the current question, or revise an earlier one. "unknown" stops the classifier there."""
    session = service.answer(db, owner, session_id, data.node_id, data.choice, ctx)
    return presenters.session_out(db, session)


@router.post("/{session_id}/restart", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def restart(session_id: uuid.UUID, owner: Owner, db: DB, ctx: Ctx) -> SessionOut:
    """A new session for the same product. This one is kept as it is."""
    return presenters.session_out(db, service.restart(db, owner, session_id, ctx))


@router.post("/{session_id}/confirm", response_model=SessionOut)
def confirm(session_id: uuid.UUID, data: ConfirmIn, owner: Owner, db: DB, ctx: Ctx) -> SessionOut:
    return presenters.session_out(db, service.confirm(db, owner, session_id, data.outcome_id, ctx))


@router.post("/{session_id}/reject", response_model=SessionOut)
def reject(session_id: uuid.UUID, data: RejectIn, owner: Owner, db: DB, ctx: Ctx) -> SessionOut:
    """Decline the proposed category. No other category is chosen in its place."""
    return presenters.session_out(db, service.reject(db, owner, session_id, data.outcome_id, data.reason, ctx))


# ---------- the tree ----------


@tree_router.get("", response_model=TreeOut)
def current_tree(_: AnyRole, db: DB) -> TreeOut:
    return presenters.tree_out(db, registry.current_tree())


@tree_router.get("/{version}", response_model=TreeOut)
def tree_version(version: int, _: AnyRole, db: DB) -> TreeOut:
    try:
        tree = registry.get_tree(version)
    except registry.UnknownTree:
        raise NotFound("Classifier tree version not found") from None
    return presenters.tree_out(db, tree)


@tree_router.post("/{version}/references/{slot_id}", response_model=SlotOut, status_code=status.HTTP_201_CREATED)
def link_reference(version: int, slot_id: str, data: ReferenceLinkIn, curator: Curator, db: DB, ctx: Ctx) -> SlotOut:
    """Point a reference slot at an approved provision version. Curators only."""
    link = service.link_reference(db, curator, version, slot_id, data.provision_version_id, ctx)
    tree = registry.get_tree(link.tree_version)
    return presenters.slot_out(db, service.reference_states(db, tree)[link.slot_id])
