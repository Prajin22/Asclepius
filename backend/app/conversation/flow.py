"""Which history flows exist, and which one a new conversation starts on.

A session records the flow id and version it started under, and every later
step of that session is walked under exactly that flow — never the current one.
That is the whole point of versioning a flow: a change to the tree cannot
reinterpret answers a patient has already given, and a conversation cannot
change shape underneath someone who is halfway through it.

Every published flow is fingerprinted below. Published flows are immutable; a
change to one is a new version, and the test that compares fingerprints is what
stops it happening by accident.
"""

from app.conversation.flows import history_general_v1, history_general_v2
from app.conversation.model import FlowDefinition

FLOW_ID = "history_general"

#: New sessions start on this version. Existing sessions keep theirs.
FLOW_VERSION = 2

FLOWS: dict[tuple[str, int], FlowDefinition] = {
    (f.flow_id, f.version): f for f in (history_general_v1.FLOW, history_general_v2.FLOW)
}

#: sha256 of each published flow's canonical form. If a test says one of these
#: no longer matches, a published flow was edited in place. Do not update the
#: hash to make the test pass: undo the edit and add a new version instead.
PUBLISHED: dict[tuple[str, int], str] = {
    ("history_general", 1): "0d9e406659c2f508abdb55430ffbb8a603e4704cac68804c2ae7b0538d42e1c2",
    ("history_general", 2): "3c47d847bd1fca6952bd5fd127b036831485d010c109ab526e2909e7ae88cda1",
}

# A malformed flow cannot be walked deterministically. Better the application
# refuses to start than asks a patient the wrong thing.
for _flow in FLOWS.values():
    _flow.validate()


class UnknownFlow(LookupError):
    """A session names a flow this build does not have.

    Never answered by substituting another flow: walking a session under a tree
    it did not start with is exactly what versioning exists to prevent.
    """


def get_flow(flow_id: str, version: int) -> FlowDefinition:
    try:
        return FLOWS[(flow_id, version)]
    except KeyError:
        raise UnknownFlow(f"{flow_id} v{version} is not available in this build") from None


def current_flow() -> FlowDefinition:
    """The flow a new conversation starts on. Read at call time."""
    return get_flow(FLOW_ID, FLOW_VERSION)
