"""Which classifier trees exist, and which one a new session starts on.

A session records the tree id, version and fingerprint it started under, and is
walked under exactly that tree for its whole life. A change to the tree is a
new version; it never reinterprets answers already given.

Every published tree's fingerprint is pinned below. If a test says one no longer
matches, a published tree was edited in place: undo the edit and add a version.
"""

from app.sakti.classifier.model import Tree
from app.sakti.classifier.trees import formulation_v1

CLASSIFIER_ID = "ip_sakti_formulation"

#: New sessions start on this version. Existing sessions keep theirs.
CURRENT_VERSION = 1

TREES: dict[tuple[str, int], Tree] = {(t.classifier_id, t.version): t for t in (formulation_v1.TREE,)}

PUBLISHED: dict[tuple[str, int], str] = {
    ("ip_sakti_formulation", 1): "579b00247af5c6362ecab1209985ed35f99a4e57c66d46e9f0010ec7157c510d",
}

# A malformed tree cannot be walked deterministically: refuse to start.
for _tree in TREES.values():
    _tree.validate()


class UnknownTree(LookupError):
    """A session names a tree this build does not have. Never answered by substituting another."""


def get_tree(version: int, classifier_id: str = CLASSIFIER_ID) -> Tree:
    try:
        return TREES[(classifier_id, version)]
    except KeyError:
        raise UnknownTree(f"{classifier_id} v{version} is not available in this build") from None


def current_tree() -> Tree:
    return get_tree(CURRENT_VERSION)
