"""IP-SAKTI product profiles (Phase 3). Mounted only when PRODUCT=ip_sakti.

A user's own products only: anyone else's is "not found". A profile holds what
the user says about their product; it is never a legal classification.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import DB, Ctx, require_roles
from app.models import User
from app.models.enums import UserRole
from app.sakti.classifier import presenters, service
from app.schemas.classification import ProductCreate, ProductOut, ProductUpdate, SessionSummary

router = APIRouter(prefix="/products", tags=["products"])

Owner = Annotated[User, Depends(require_roles(UserRole.USER))]


def _fields(data: ProductCreate | ProductUpdate, only_set: bool) -> dict:
    keys = data.model_fields_set if only_set else type(data).model_fields.keys()
    values = data.model_dump(include=set(keys))
    return values


@router.get("", response_model=list[ProductOut])
def list_products(owner: Owner, db: DB) -> list[ProductOut]:
    return [presenters.product_out(db, p) for p in service.list_products(db, owner)]


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductCreate, owner: Owner, db: DB, ctx: Ctx) -> ProductOut:
    return presenters.product_out(db, service.create_product(db, owner, _fields(data, only_set=False), ctx))


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: uuid.UUID, owner: Owner, db: DB) -> ProductOut:
    return presenters.product_out(db, service.get_own_product(db, owner, product_id))


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(product_id: uuid.UUID, data: ProductUpdate, owner: Owner, db: DB, ctx: Ctx) -> ProductOut:
    changes = _fields(data, only_set=True)
    if changes.get("name", "") is None:
        changes.pop("name")  # a product always has a name
    for key in ("ingredients", "markers"):
        if key in changes and changes[key] is None:
            changes[key] = []
    return presenters.product_out(db, service.update_product(db, owner, product_id, changes, ctx))


@router.get("/{product_id}/classifications", response_model=list[SessionSummary])
def product_classifications(product_id: uuid.UUID, owner: Owner, db: DB) -> list[SessionSummary]:
    """Every classification session of this product, newest first. None is ever deleted."""
    return [presenters.session_summary(db, s) for s in service.sessions_for_product(db, owner, product_id)]
