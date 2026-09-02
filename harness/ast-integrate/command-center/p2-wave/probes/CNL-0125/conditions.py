"""The 12 completion conditions, quoted not paraphrased.

Source on this estate: WFA-0042 captured _USER-PROMPTS.md:10627-10648
(the Windows harness path is not mounted here). Numbering is 1-12 as at
lines 10631-10644. The three anti-patterns are line 10646.
"""
from __future__ import annotations

SPEC_LOCUS = (
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10627-10648"
)
SPEC_CAPTURE = (
    "command-center/p2-wave/probes/WFA-0042/_validate_out.json"
    "#gate_a_unit_completion_predicate.conditions"
)

# Verbatim numbered list (as in the spec capture).
CONDITIONS: list[tuple[int, str]] = [
    (1, "process/task reached a valid terminal state"),
    (2, "expected artifact exists"),
    (3, "artifact is non-empty and exceeds a meaningful minimum size"),
    (4, "artifact parses against its schema"),
    (5, "required sentinel is present"),
    (6, "required evidence anchors exist"),
    (7, "required tests ran and passed"),
    (8, "negative controls or mutations fail as expected"),
    (9, "independent reviewer status is PASS"),
    (10, "no unresolved P0/P1 defect is attached"),
    (11, "output was registered in the artifact manifest"),
    (12, "downstream consumers can read it"),
]

ANTI_PATTERNS = (
    "Exit code zero alone is never success. "
    "A plausible digest is not a receipt. "
    "A file path in text is not proof the file exists."
)

MIN_BYTES = 128
CONSUMER_FIELDS = ("sentinel", "recommendation", "lineage_root", "dissent")
COMPLETION_STATES = frozenset({"SUCCESS"})
TERMINAL_NON_COMPLETION = frozenset({"BLOCKED", "FAILED", "TIMEOUT", "SEVERED"})
OPEN_P0_P1 = frozenset({"P0", "P1"})
