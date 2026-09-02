"""The 12 unit-completion conditions.

Source: spec lines 10631-10644 as recorded in
command-center/p2-wave/_build_IMP0433.py (read from
gate_a_unit_completion_predicate) and the same numbered list in
command-center/p2-wave/probes/WFA-0042/_validate_out.json. COMPLETION-GATES.json
is absent on this worktree; this list is the reconstructed gate text, not a
paraphrase of a different numbering.
"""

from __future__ import annotations

CONDITIONS: tuple[str, ...] = (
    "process/task reached a valid terminal state",
    "expected artifact exists",
    "artifact is non-empty and exceeds a meaningful minimum size",
    "artifact parses against its schema",
    "required sentinel is present",
    "required evidence anchors exist",
    "required tests ran and passed",
    "negative controls or mutations fail as expected",
    "independent reviewer status is PASS",
    "no unresolved P0/P1 defect is attached",
    "output was registered in the artifact manifest",
    "downstream consumers can read it",
)

HARD_RULES: tuple[str, ...] = (
    "Exit code zero alone is never success.",
    "A plausible digest is not a receipt.",
    "A file path in text is not proof the file exists.",
)

COMPLETION_STATES = frozenset({"SUCCESS"})
TERMINAL_STATES = frozenset(
    {"SUCCESS", "PARTIAL", "BLOCKED", "FAILED", "TIMEOUT", "SEVERED"}
)
OPEN = frozenset({"open", "OPEN", "unresolved", "UNRESOLVED"})
P0P1 = frozenset({"P0", "P1", "p0", "p1"})
SHA256_RE = r"^[0-9a-fA-F]{64}$"
