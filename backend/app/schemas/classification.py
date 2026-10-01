"""Shapes of the product-profile and classifier API (IP-SAKTI Phase 3).

A profile request carries the user's own description of their product and
nothing else: no field holds a classification or a legal conclusion. An answer
is a node id and one of that node's choice ids — never free text — so nothing a
user types can steer the tree.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.languages import LanguageCode
from app.models.enums import (
    AdministrationRoute,
    ClassificationStatus,
    CorpusLane,
    FormulationCategory,
    OutcomeKind,
    ReferenceStatus,
    SourceAuthority,
)

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Text2k = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Text5k = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- product profiles ----------


class Ingredient(_Strict):
    name: Name
    part_used: Short | None = None
    quantity: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None


class ProductFields(_Strict):
    intended_use: Text2k | None = None
    dosage_form: Short | None = None
    administration_route: AdministrationRoute | None = None
    ingredients: list[Ingredient] = Field(default_factory=list, max_length=100)
    preparation_method: Text5k | None = None
    classical_reference: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None
    extract_description: Text2k | None = None
    standardization_description: Text2k | None = None
    markers: list[Name] = Field(default_factory=list, max_length=50)
    notes: Text2k | None = None
    text_language: LanguageCode | None = None


class ProductCreate(ProductFields):
    name: Name


class ProductUpdate(ProductFields):
    """Only the fields sent are changed; a field sent as null is cleared."""

    name: Name | None = None


class ConfirmedClassification(BaseModel):
    session_id: uuid.UUID
    outcome_id: uuid.UUID
    category: FormulationCategory
    tree_version: int
    decided_at: datetime


class ProductOut(BaseModel):
    id: uuid.UUID
    name: str
    intended_use: str | None
    dosage_form: str | None
    administration_route: AdministrationRoute | None
    ingredients: list[dict[str, Any]]
    preparation_method: str | None
    classical_reference: str | None
    extract_description: str | None
    standardization_description: str | None
    markers: list[str]
    notes: str | None
    text_language: LanguageCode | None
    revision: int
    created_at: datetime
    updated_at: datetime
    #: The user's own confirmed classification, if any. Never a legal determination.
    confirmed_classification: ConfirmedClassification | None = None
    open_session_id: uuid.UUID | None = None


# ---------- the tree ----------


class ChoiceOut(BaseModel):
    id: str
    label_key: str


class NodeOut(BaseModel):
    id: str
    question_key: str
    help_key: str
    missing_key: str
    why_key: str
    choices: list[ChoiceOut]
    context_fields: list[str]
    references: list[str]


class ProvisionPointer(BaseModel):
    """Approved, stored corpus metadata for a verified reference. Never quoted text."""

    provision_version_id: uuid.UUID
    locator: str
    version_number: int
    instrument_title: str
    source_title: str
    source_authority: SourceAuthority


class SlotOut(BaseModel):
    id: str
    lane: CorpusLane
    describes_key: str
    status: ReferenceStatus
    provision: ProvisionPointer | None = None


class TreeOut(BaseModel):
    classifier_id: str
    version: int
    fingerprint: str
    current: bool
    status: str
    legal_review: str
    start: str
    nodes: list[NodeOut]
    categories: list[FormulationCategory]
    slots: list[SlotOut]


class ReferenceLinkIn(_Strict):
    provision_version_id: uuid.UUID


# ---------- sessions ----------


class StepOut(BaseModel):
    node_id: str
    choice: str


class AnswerOut(BaseModel):
    node_id: str
    choice: str
    answered_at: datetime
    superseded_at: datetime | None


class OutcomeReference(BaseModel):
    slot_id: str
    status: ReferenceStatus
    provision_version_id: uuid.UUID | None


class OutcomeOut(BaseModel):
    id: uuid.UUID
    sequence: int
    kind: OutcomeKind
    category: FormulationCategory | None
    stop_node_id: str | None
    path: list[StepOut]
    answers_sha256: str
    tree_version: int
    #: Each reference slot's status when this outcome was reached.
    references: list[OutcomeReference]
    created_at: datetime


class SessionSummary(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    status: ClassificationStatus
    tree_version: int
    category: FormulationCategory | None
    created_at: datetime
    decided_at: datetime | None
    restarted_from_id: uuid.UUID | None


class SessionOut(SessionSummary):
    product_name: str
    classifier_id: str
    tree_fingerprint: str
    current_node_id: str | None
    path: list[StepOut]
    latest_outcome: OutcomeOut | None
    outcomes: list[OutcomeOut]
    answer_history: list[AnswerOut]
    #: The current status of every reference slot the latest outcome rests on.
    references: list[SlotOut]
    product_revision: int
    product_snapshot: dict[str, Any]
    decided_outcome_id: uuid.UUID | None
    rejection_reason: str | None
    updated_at: datetime


class StartSession(_Strict):
    product_id: uuid.UUID


class AnswerIn(_Strict):
    node_id: Slug
    choice: Slug


class ConfirmIn(_Strict):
    #: The outcome the user is looking at; refused if it is no longer the latest.
    outcome_id: uuid.UUID


class RejectIn(ConfirmIn):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None
