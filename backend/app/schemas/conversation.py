"""History-conversation schemas.

The shape of these is the safety property, the same way it is in Phase 4:

* a client says **what it is answering**, never **what to ask next**. There is
  no `next_question_id` anywhere in this file, no flow version in any request,
  and unknown fields are refused — so a caller cannot steer the conversation,
  pick the tree, or smuggle a field past the server.
* an answer's controlled form is a closed vocabulary — option ids and a
  duration — so a client cannot write arbitrary JSON into a patient's record.
* no wording crosses the wire. Questions, options, help and reasons travel as
  localisation keys and reason codes; the browser renders them in the
  patient's language.
* every flow says what it is: `engineering_draft`, `clinical_review: required`.

Nothing here can express a diagnosis, a severity, a risk score or a triage
level, because no field exists to hold one.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.languages import LanguageCode
from app.models.enums import (
    ConversationSection,
    ConversationStatus,
    FactCategory,
    FactReviewState,
    FactSubject,
    RecordType,
    ResponseType,
)

#: An option id as it appears in a flow definition — a slug, never a label.
OptionId = Annotated[str, StringConstraints(strip_whitespace=True, max_length=40, pattern=r"^[a-z0-9_]+$")]

#: Matches `app.conversation.engine.MAX_ANSWER_CHARS`. Longer is refused, not
#: quietly shortened.
MAX_ANSWER_CHARS = 2000
MAX_VALUE_CHARS = 300

AnswerText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_ANSWER_CHARS)]
CandidateValue = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_VALUE_CHARS)]
IdempotencyKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=64)]


# --------------------------------------------------------------------------
# what the server offers
# --------------------------------------------------------------------------


class ReasonOut(BaseModel):
    """Why a question was asked, or why it was not. Machine-readable.

    Rendered from `conversation.reason.<code>`. Never an English sentence.
    """

    model_config = ConfigDict(extra="forbid")

    code: str
    #: The earlier question whose answer decided this, when a branch did.
    trigger_question_id: str | None = None
    predicate_id: str | None = None


class OptionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: OptionId
    #: Localisation key. The label itself is resolved in the browser.
    label_key: str
    #: A complete answer on its own ("none of these", "not sure").
    exclusive: bool = False


class QuestionOut(BaseModel):
    """The question the conversation is waiting on, and why it was chosen."""

    model_config = ConfigDict(extra="forbid")

    id: str
    version: int
    section: ConversationSection
    response_type: ResponseType
    prompt_key: str
    help_key: str | None = None
    options: list[OptionOut] = Field(default_factory=list)
    required: bool = True
    reason: ReasonOut | None = None


# --------------------------------------------------------------------------
# what a client may send
# --------------------------------------------------------------------------


class DurationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: float = Field(gt=0, le=1200)
    unit: Literal["hours", "days", "weeks", "months", "years"]


class AnswerValueIn(BaseModel):
    """The controlled part of an answer.

    Closed on purpose. `bool` is absent because the server derives it from the
    chosen option rather than letting a client assert it.
    """

    model_config = ConfigDict(extra="forbid")

    choices: list[OptionId] | None = Field(default=None, max_length=12)
    duration: DurationIn | None = None


class ConversationStartIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Defaults to the patient's own preferred language.
    language: LanguageCode | None = None


class _AnswerFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Supplied by the client so a retried submission is recognised as the same
    #: request. A UUID is the obvious choice.
    idempotency_key: IdempotencyKey
    text: AnswerText | None = None
    value: AnswerValueIn | None = None
    #: The patient chose not to answer an optional question. Refused on a
    #: required one; every required tap question offers "not sure" instead.
    declined: bool = False
    #: The revision the client last saw. When it no longer matches, the request
    #: is refused instead of two requests both moving the conversation.
    expected_revision: int | None = Field(default=None, ge=0)


class AnswerIn(_AnswerFields):
    """An answer to the question the conversation is currently on.

    `question_id` says what is being answered so a stale client is told rather
    than silently advanced. It is not a request to jump there.
    """

    question_id: Annotated[str, StringConstraints(strip_whitespace=True, max_length=64)]


class AnswerRevisionIn(_AnswerFields):
    """A replacement for an earlier answer. The question is named in the path."""


class CandidateActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["confirm", "edit", "reject"]
    #: Required for "edit", ignored otherwise.
    value: CandidateValue | None = None


# --------------------------------------------------------------------------
# what a client receives
# --------------------------------------------------------------------------


class ResponseOut(BaseModel):
    """One answer as it was given. `answer_text` is never a normalised form."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    question_id: str
    question_version: int
    section: ConversationSection
    response_type: ResponseType
    answer_text: str | None = None
    answer_language: LanguageCode | None = None
    answer_value: dict = Field(default_factory=dict)
    #: "No answer" — the patient chose not to answer. Never "not applicable".
    declined: bool = False
    #: Why the question was asked when this answer was given.
    reason: ReasonOut | None = None
    sequence: int
    created_at: datetime


class CandidateOut(BaseModel):
    """Something an answer might mean, until the patient says it does."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    response_id: uuid.UUID
    category: FactCategory
    subject: FactSubject
    value: str
    edited_value: str | None = None
    #: What the patient stands behind: their edit if any, else the value.
    effective_value: str
    #: The words the answer was given in, kept beside the value.
    original_text: str | None = None
    review_state: FactReviewState
    reviewed_at: datetime | None = None
    #: Set once confirming this wrote a health record from it.
    medical_record_id: uuid.UUID | None = None


class ConversationOut(BaseModel):
    """Where the conversation is, and what it is waiting on."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    flow_id: str
    flow_version: int
    #: `engineering_draft` — carried on every payload so no screen built on
    #: this can present the flow as something it is not.
    flow_status: str
    #: `required` — no clinician has reviewed this flow.
    clinical_review: str
    status: ConversationStatus
    language: LanguageCode
    #: Echoed back so the next request can be checked against it.
    revision: int
    current_section: ConversationSection | None = None
    #: The current question's id, `review.confirm` once only review remains,
    #: or null when the conversation is closed.
    current_step: str | None = None
    question: QuestionOut | None = None
    answered: int
    #: Applicable questions known to be left. Follow-ups not yet decided are
    #: not counted, so this is a floor.
    remaining: int
    started_at: datetime
    paused_at: datetime | None = None
    completed_at: datetime | None = None


class ConversationDetailOut(ConversationOut):
    responses: list[ResponseOut] = Field(default_factory=list)
    candidates: list[CandidateOut] = Field(default_factory=list)


# --------------------------------------------------------------------------
# review
# --------------------------------------------------------------------------


class ReviewItemOut(BaseModel):
    """One question and where it stands. Listed in the flow's own order."""

    model_config = ConfigDict(extra="forbid")

    question_id: str
    question_version: int
    section: ConversationSection
    response_type: ResponseType
    prompt_key: str
    #: `answered`, `declined` ("no answer"), `not_applicable` ("not asked") or
    #: `current`. Kept as four values because they are four different facts.
    outcome: Literal["answered", "declined", "not_applicable", "current"]
    response: ResponseOut | None = None
    reason: ReasonOut | None = None


class ReviewCandidateOut(CandidateOut):
    #: The health record confirming this would create, or null when it would
    #: create none. Shown so the patient knows what they are agreeing to.
    becomes: RecordType | None = None


class ReviewCountsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answered: int
    declined: int
    not_applicable: int
    candidates_pending: int
    candidates_confirmed: int
    candidates_edited: int
    candidates_rejected: int


class ReviewOut(BaseModel):
    """What the patient has said, before any of it counts.

    Showing this confirms nothing. Only an explicit action on a candidate does.
    """

    model_config = ConfigDict(extra="forbid")

    conversation: ConversationOut
    #: True when every applicable question is resolved and the conversation can
    #: be closed. Pending candidates do not block it: completing confirms nothing.
    can_complete: bool
    items: list[ReviewItemOut]
    candidates: list[ReviewCandidateOut]
    counts: ReviewCountsOut
