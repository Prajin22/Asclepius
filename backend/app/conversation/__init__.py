"""The conversational history engine (Phase 5).

A controlled patient-history collection workflow, not a chatbot. The
application owns the questions, their order, when each applies, what a valid
answer is, confirmation, persistence and completion. No model decides anything
here. When interpretation arrives (Phase 5C) it will sit between an answer and
a candidate, and a patient will still have to confirm what it suggests.

    model   the vocabulary a flow is written in
    engine  pure, deterministic decisions: what applies, what is next, what is valid
    flows   the published flows, one module per version
    flow    the registry, and which version a new conversation starts on
"""

from app.conversation.flow import FLOW_ID, FLOW_VERSION, FLOWS, current_flow, get_flow
from app.conversation.model import (
    REVIEW_STEP_ID,
    Answer,
    Branch,
    FlowDefinition,
    Option,
    QuestionDefinition,
    Resolution,
    Selection,
    Status,
)

__all__ = [
    "FLOW_ID",
    "FLOW_VERSION",
    "FLOWS",
    "REVIEW_STEP_ID",
    "Answer",
    "Branch",
    "FlowDefinition",
    "Option",
    "QuestionDefinition",
    "Resolution",
    "Selection",
    "Status",
    "current_flow",
    "get_flow",
]
