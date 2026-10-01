from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.languages import LanguageCode
from app.db.base import Base, JSONType, Timestamps, UUIDPrimaryKey, enum_column, utcnow
from app.models.enums import (
    ConversationSection,
    ConversationStatus,
    FactCategory,
    FactReviewState,
    FactSubject,
    ResponseType,
)

#: A row that has been replaced stays, marked with when; only one is current.
_CURRENT = sa.text("superseded_at IS NULL")
#: The statuses in which a conversation is still the patient's current one.
_OPEN = sa.text("status IN ('awaiting_answer', 'awaiting_confirmation', 'paused')")


class ConversationSession(UUIDPrimaryKey, Timestamps, Base):
    """One run through a history flow, by one patient.

    The session records which flow version it started under, and is walked
    under that version for its whole life. `current_*` is where the engine has
    got to and why; the answers themselves live in `conversation_responses`,
    and questions the engine passed over in `conversation_skips`.

    This is a workflow, not a second home for patient information. Nothing here
    is visible to a doctor by existing itself — sharing stays with the
    consultation mechanism it already has.
    """

    __tablename__ = "conversation_sessions"
    __table_args__ = (
        sa.Index("ix_conversation_sessions_patient_status", "patient_id", "status"),
        # One open conversation per patient, held by the database rather than
        # by a check two simultaneous requests could both pass.
        sa.Index(
            "uq_conversation_sessions_one_open",
            "patient_id",
            unique=True,
            postgresql_where=_OPEN,
            sqlite_where=_OPEN,
        ),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    flow_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    flow_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    status: Mapped[ConversationStatus] = mapped_column(
        enum_column(ConversationStatus, "conversation_status"),
        nullable=False,
        default=ConversationStatus.AWAITING_ANSWER,
        server_default=ConversationStatus.AWAITING_ANSWER.value,
    )
    #: The language the patient is answering in. Question text is resolved from
    #: a localisation key at render time, so this describes the answers only.
    language: Mapped[LanguageCode] = mapped_column(
        enum_column(LanguageCode, "conversation_language"),
        nullable=False,
        default=LanguageCode.EN,
        server_default=LanguageCode.EN.value,
    )

    current_section: Mapped[ConversationSection | None] = mapped_column(
        enum_column(ConversationSection, "conversation_section")
    )
    current_question_id: Mapped[str | None] = mapped_column(sa.String(64))
    #: The wording the patient is actually being shown, so an answer can always
    #: be read against the question as it stood.
    current_question_version: Mapped[int | None] = mapped_column(sa.Integer)
    #: Why the engine chose it, as a reason code (`radiation_reported`,
    #: `flow_sequence`). Machine-readable, rendered in the browser from
    #: `conversation.reason.<code>`; never an English sentence.
    current_question_reason: Mapped[str | None] = mapped_column(sa.String(300))
    #: The earlier question whose answer opened this one, when a branch did.
    current_trigger_question_id: Mapped[str | None] = mapped_column(sa.String(64))
    current_predicate_id: Mapped[str | None] = mapped_column(sa.String(64))

    #: Optimistic concurrency token, enforced by the database: every UPDATE of
    #: this row carries `WHERE revision = <the value that was read>`, so of two
    #: requests that read the same revision only the first can write. The
    #: application sets the new value itself, once per accepted transition.
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0, server_default="0")

    started_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow, server_default=sa.func.now()
    )
    paused_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    responses: Mapped[list[ConversationResponse]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ConversationResponse.sequence"
    )
    candidates: Mapped[list[ConversationCandidateFact]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ConversationCandidateFact.position"
    )
    skips: Mapped[list[ConversationSkip]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ConversationSkip.sequence"
    )

    __mapper_args__ = {"version_id_col": revision, "version_id_generator": False}

    @property
    def is_active(self) -> bool:
        """Open for answers or review. `active` is this, not a stored state."""
        return self.status in (ConversationStatus.AWAITING_ANSWER, ConversationStatus.AWAITING_CONFIRMATION)


class ConversationResponse(UUIDPrimaryKey, Base):
    """One answer, in the patient's own words, against one question.

    Append-only. Revising an answer marks this row superseded and adds a new
    one; the earlier answer is still something the patient said, and it stays.
    At most one response per question is current at a time, and the database
    enforces it.

    `answer_text` is never normalised or translated. `answer_value` holds the
    controlled form — the option ids tapped, the duration — so a tapped answer
    means the same thing whatever language it was tapped in.
    """

    __tablename__ = "conversation_responses"
    __table_args__ = (
        sa.UniqueConstraint("session_id", "idempotency_key", name="uq_conversation_response_idempotency"),
        sa.Index("ix_conversation_responses_session_current", "session_id", "superseded_at"),
        sa.Index(
            "uq_conversation_responses_current_answer",
            "session_id",
            "question_id",
            unique=True,
            postgresql_where=_CURRENT,
            sqlite_where=_CURRENT,
        ),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("conversation_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    question_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    #: The wording the patient saw. Keeps old answers readable after a rewording.
    question_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    section: Mapped[ConversationSection] = mapped_column(
        enum_column(ConversationSection, "response_section"), nullable=False
    )
    response_type: Mapped[ResponseType] = mapped_column(
        enum_column(ResponseType, "response_type"), nullable=False
    )

    #: Exactly what the patient typed. Never rewritten.
    answer_text: Mapped[str | None] = mapped_column(sa.Text)
    #: The language they typed it in. Null for a tap: a tap has no language.
    answer_language: Mapped[LanguageCode | None] = mapped_column(
        enum_column(LanguageCode, "answer_language")
    )
    #: Controlled form: {"choices": [...]} | {"choices": ["yes"], "bool": true} | {"duration": {...}}
    answer_value: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    #: The patient chose not to answer an optional question — "no answer". This
    #: never means "not applicable": a question the engine did not ask has no
    #: response at all, only a row in `conversation_skips`.
    declined: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.false())

    #: Why the question was asked when this answer was given. Reason codes, as
    #: on the session; null only on rows written before Phase 5B.
    reason_code: Mapped[str | None] = mapped_column(sa.String(64))
    trigger_question_id: Mapped[str | None] = mapped_column(sa.String(64))
    predicate_id: Mapped[str | None] = mapped_column(sa.String(64))

    sequence: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    #: Supplied by the client so a retried submission is the same answer, not a
    #: second one. Unique per session.
    idempotency_key: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    superseded_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow, server_default=sa.func.now()
    )

    session: Mapped[ConversationSession] = relationship(back_populates="responses")


class ConversationSkip(UUIDPrimaryKey, Base):
    """A question the engine did not ask, and exactly why. Never an answer.

    "Not asked" and "no" are different facts. When a branch stays shut the
    engine records the question here, with the reason code, the trigger and the
    predicate — and records nothing as the patient's answer, because the
    patient was not asked. A revision upstream can reopen the question; the row
    is then superseded, not deleted.
    """

    __tablename__ = "conversation_skips"
    __table_args__ = (
        sa.Index("ix_conversation_skips_session_current", "session_id", "superseded_at"),
        sa.Index(
            "uq_conversation_skips_current",
            "session_id",
            "question_id",
            unique=True,
            postgresql_where=_CURRENT,
            sqlite_where=_CURRENT,
        ),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("conversation_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    question_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    flow_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    section: Mapped[ConversationSection] = mapped_column(
        enum_column(ConversationSection, "skip_section"), nullable=False
    )
    reason_code: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    trigger_question_id: Mapped[str | None] = mapped_column(sa.String(64))
    predicate_id: Mapped[str | None] = mapped_column(sa.String(64))
    sequence: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    superseded_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow, server_default=sa.func.now()
    )

    session: Mapped[ConversationSession] = relationship(back_populates="skips")


class ConversationCandidateFact(UUIDPrimaryKey, Base):
    """Something an answer might mean, until the patient says it does.

    The same shape of promise Phase 2 makes: a candidate is a suggestion, it
    carries the words it came from, and it becomes part of the patient's record
    only when they confirm it. Category, attribution and review state reuse the
    Phase 2 vocabulary rather than inventing a parallel one.

    Evidence here is the conversation itself — which question, which wording,
    which answer — rather than a quote and an offset.
    """

    __tablename__ = "conversation_candidate_facts"
    __table_args__ = (
        sa.Index("ix_conversation_candidates_session_state", "session_id", "review_state"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("conversation_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    response_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("conversation_responses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    category: Mapped[FactCategory] = mapped_column(
        enum_column(FactCategory, "candidate_category"), nullable=False
    )
    #: Whose health this describes — from the question that was asked.
    subject: Mapped[FactSubject] = mapped_column(
        enum_column(FactSubject, "candidate_subject"),
        nullable=False,
        default=FactSubject.SELF,
        server_default=FactSubject.SELF.value,
    )
    subject_evidence: Mapped[str | None] = mapped_column(sa.String(200))

    #: The controlled value a confirmed candidate would contribute.
    value: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    #: The patient's own words for it. Kept beside the value, never replaced by it.
    original_text: Mapped[str | None] = mapped_column(sa.Text)

    review_state: Mapped[FactReviewState] = mapped_column(
        enum_column(FactReviewState, "candidate_review_state"),
        nullable=False,
        default=FactReviewState.PENDING,
        server_default=FactReviewState.PENDING.value,
    )
    edited_value: Mapped[str | None] = mapped_column(sa.String(300))
    reviewed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    #: Set when confirming this candidate wrote a health record from it.
    medical_record_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("medical_records.id", ondelete="SET NULL")
    )
    #: Set when the answer it came from was revised. A superseded candidate is
    #: no longer offered for review and can no longer be acted on; it stays so
    #: the history of what was suggested is intact.
    superseded_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    position: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow, server_default=sa.func.now()
    )

    session: Mapped[ConversationSession] = relationship(back_populates="candidates")

    @property
    def effective_value(self) -> str:
        """What the patient stands behind: their edit if any, else the value."""
        return self.edited_value or self.value
