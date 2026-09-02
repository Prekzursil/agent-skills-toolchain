"""Shared labels for the 12-condition unit completion predicate.

Evaluation logic is NOT here. The production fan-in (`runner_fanin.py`) wraps
`platform/lib/completion_predicate.evaluate`. The reference oracle (`oracle.py`)
implements the same 12 conditions independently. This module only names the
conditions so comparison tables use one id vocabulary.
"""
from __future__ import annotations

CONDITIONS: tuple[tuple[str, str], ...] = (
    ("C1", "process/task reached a valid terminal state"),
    ("C2", "expected artifact exists"),
    ("C3", "artifact is non-empty and exceeds a meaningful minimum size"),
    ("C4", "artifact parses against its schema"),
    ("C5", "required sentinel is present"),
    ("C6", "required evidence anchors exist"),
    ("C7", "required tests ran and passed"),
    ("C8", "negative controls or mutations fail as expected"),
    ("C9", "independent reviewer status is PASS"),
    ("C10", "no unresolved P0/P1 defect is attached"),
    ("C11", "output was registered in the artifact manifest"),
    ("C12", "downstream consumers can read it"),
)

CONDITION_IDS: tuple[str, ...] = tuple(cid for cid, _ in CONDITIONS)
CONDITION_TEXT: dict[str, str] = {cid: text for cid, text in CONDITIONS}

TERMINAL_STATES: frozenset[str] = frozenset(
    {"SUCCESS", "FAILED", "BLOCKED", "TIMEOUT", "SEVERED", "PARTIAL"}
)

OPEN_DEFECT_STATUSES: frozenset[str] = frozenset(
    {"open", "unresolved", "OPEN", "UNRESOLVED"}
)
BLOCKING_SEVERITIES: frozenset[str] = frozenset({"P0", "P1"})
