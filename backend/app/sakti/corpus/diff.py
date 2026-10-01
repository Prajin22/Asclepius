"""A deterministic diff between two texts: lines first, then words inside changed lines.

Python's difflib, nothing else. The same two texts always give the same diff,
and the diff only says which characters differ — never what a change means.
No model decides whether legal text changed, and nothing here summarises a
change in words of its own.

Long unchanged runs are folded to `CONTEXT` lines either side; the number of
lines folded away is reported, so nothing is hidden without saying so.
"""

import re
from difflib import SequenceMatcher
from typing import Any

CONTEXT = 3
_TOKEN = re.compile(r"\s+|\w+|[^\w\s]", re.UNICODE)


def _lines(text: str) -> list[str]:
    # splitlines() also breaks on the form feed between pages.
    return text.splitlines()


def word_diff(old: str, new: str) -> list[dict[str, str]]:
    """Inline parts: {"op": "equal" | "delete" | "insert", "text": ...}, in order."""
    a, b = _TOKEN.findall(old), _TOKEN.findall(new)
    parts: list[dict[str, str]] = []

    def add(op: str, tokens: list[str]) -> None:
        if not tokens:
            return
        text = "".join(tokens)
        if parts and parts[-1]["op"] == op:
            parts[-1]["text"] += text
        else:
            parts.append({"op": op, "text": text})

    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            add("equal", a[i1:i2])
        else:
            add("delete", a[i1:i2])
            add("insert", b[j1:j2])
    return parts


def diff_texts(old: str, new: str, context: int = CONTEXT) -> dict[str, Any]:
    """Blocks of equal / insert / delete / replace lines, with line numbers (1-based)."""
    a, b = _lines(old), _lines(new)
    opcodes = SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
    blocks: list[dict[str, Any]] = []
    stats = {"added": 0, "removed": 0, "changed": 0, "unchanged": 0}

    for index, (tag, i1, i2, j1, j2) in enumerate(opcodes):
        block: dict[str, Any] = {"op": tag, "old_start": i1 + 1, "new_start": j1 + 1}
        if tag == "equal":
            lines = a[i1:i2]
            stats["unchanged"] += len(lines)
            first, last = index == 0, index == len(opcodes) - 1
            # Context is kept only next to a change: before it, after it, or both.
            head = [] if first else lines[:context]
            tail = [] if last else lines[-context:]
            if first and last:
                head, tail = [], []  # nothing changed at all
            elif len(head) + len(tail) >= len(lines):
                head, tail = lines, []
            block.update(lines=head, skipped=len(lines) - len(head) - len(tail), tail=tail)
        elif tag == "insert":
            stats["added"] += j2 - j1
            block.update(new=b[j1:j2])
        elif tag == "delete":
            stats["removed"] += i2 - i1
            block.update(old=a[i1:i2])
        else:  # replace
            paired = min(i2 - i1, j2 - j1)
            stats["changed"] += paired
            stats["removed"] += (i2 - i1) - paired
            stats["added"] += (j2 - j1) - paired
            block.update(old=a[i1:i2], new=b[j1:j2], words=word_diff("\n".join(a[i1:i2]), "\n".join(b[j1:j2])))
        blocks.append(block)
    return {"stats": stats, "blocks": blocks}
