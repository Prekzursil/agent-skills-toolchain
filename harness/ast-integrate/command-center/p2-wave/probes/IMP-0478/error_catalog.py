#!/usr/bin/env python3
"""User-facing error catalog for the closed IMP-0449 failure taxonomy.

Every closed class maps to a message that names (1) what failed, (2) why, and
(3) the exact next command. Mapping is structural: a class with a missing part,
an empty part, or a traceback-only body is UNMAPPED, not "covered by prose".

Taxonomy source: the closed class list in WORK-UNIT-CATALOG.json IMP-0449
`question_or_target` (IMP-0449's receipt is not on this worktree). This unit
does not invent extra classes as if they were in that closed set.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

# Closed set from IMP-0449. Order is the catalog's order, not a priority ranking.
CLOSED_TAXONOMY: tuple[str, ...] = (
    "severed-stream",
    "adapter-exit-n",
    "win-arg-limit",
    "timeout",
    "schema-invalid",
    "partial-artifact",
    "degraded",
    "blocked",
)

# Terminal state for leftovers (IMP-0449 exhaustiveness test). Not one of the
# eight closed classes; mapped so a naive user still gets a next command.
UNCLASSIFIED = "unclassified"

DOCTOR = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0478/doctor.py"
)

_TRACEBACK_MARK = "Traceback (most recent call last)"


def next_command_for(taxonomy_class: str) -> str:
    """Exact next command a naive user can paste at the repo root."""
    return f"{DOCTOR} --class {taxonomy_class}"


def _entry(
    message_id: str,
    what_failed: str,
    why: str,
    taxonomy_class: str,
    hint: str,
) -> dict[str, str]:
    return {
        "taxonomy_class": taxonomy_class,
        "message_id": message_id,
        "what_failed": what_failed,
        "why": why,
        "next_command": next_command_for(taxonomy_class),
        "hint": hint,
    }


# SSOT. Keys are taxonomy class ids. Values are the user-facing records.
CATALOG: dict[str, dict[str, str]] = {
    "severed-stream": _entry(
        "MSG-SEVERED-STREAM",
        "The adapter stream ended before a terminal receipt arrived.",
        "A progress-only or cut-off stream is not a result; treating it as "
        "success would invent a verdict the adapter never emitted.",
        "severed-stream",
        "Re-dispatch in the foreground. Do not classify a progress stream or a "
        "missing output file as SUCCESS, even if the process exit code was 0.",
    ),
    "adapter-exit-n": _entry(
        "MSG-ADAPTER-EXIT-N",
        "The adapter process exited with a non-zero code before producing a "
        "valid receipt.",
        "Exit N without a classified receipt is a tool failure, not a unit "
        "verdict, and must not be rewritten into SUCCESS.",
        "adapter-exit-n",
        "Capture stderr, keep the numeric exit, and re-run only after the "
        "adapter command itself is fixed. Do not retry a logic failure.",
    ),
    "win-arg-limit": _entry(
        "MSG-WIN-ARG-LIMIT",
        "The Windows argument-length limit rejected the dispatch command line.",
        "The prompt was passed as argv instead of a prompt file, so the OS "
        "refused to start the adapter.",
        "win-arg-limit",
        "Retry ONCE with --ignore-user-config and a --prompt-file transport. "
        "A second win-arg-limit is BLOCKED, not another argv retry.",
    ),
    "timeout": _entry(
        "MSG-TIMEOUT",
        "The unit hit its time budget before a terminal state.",
        "No receipt arrived inside timeout_seconds, so waiting longer without "
        "a new budget would be an unbounded hang.",
        "timeout",
        "Inspect the last probe output, then re-dispatch with an explicit "
        "budget only if the hang was environmental. Do not auto-retry a "
        "logic failure.",
    ),
    "schema-invalid": _entry(
        "MSG-SCHEMA-INVALID",
        "The artifact exists but does not parse against its declared schema.",
        "A file that fails its contract is not evidence. Retrying without "
        "fixing the schema or the document repeats the same invalid bytes.",
        "schema-invalid",
        "Do not retry the same document. Fix the schema or the instance, then "
        "re-dispatch.",
    ),
    "partial-artifact": _entry(
        "MSG-PARTIAL-ARTIFACT",
        "The output path is missing, empty, or truncated.",
        "A zero-byte or half-written file is not a completed artifact, even "
        "when a process printed SUCCESS.",
        "partial-artifact",
        "Remove the truncated file, re-run the emitter, and confirm the path "
        "is non-empty before treating the unit as delivered.",
    ),
    "degraded": _entry(
        "MSG-DEGRADED",
        "The unit finished with a usable but reduced result (P2-degraded).",
        "Some required evidence is missing or a non-blocking class fired. "
        "Raising degraded to SUCCESS hides the gap.",
        "degraded",
        "Read residual_unknowns in the receipt and close the named gap. Do "
        "not flip state to SUCCESS until that gap is gone.",
    ),
    "blocked": _entry(
        "MSG-BLOCKED",
        "The unit cannot proceed on this worktree.",
        "A named required_fix is missing (dependency, permission, or a "
        "repeated structural refute). Re-running the same command will not "
        "unblock it.",
        "blocked",
        "Stop. Apply the named required_fix. Do not start an ADV rebuild "
        "circle.",
    ),
    UNCLASSIFIED: _entry(
        "MSG-UNCLASSIFIED",
        "The error did not match any closed taxonomy class.",
        "An open-ended prose result is forbidden. UNCLASSIFIED is the explicit "
        "terminal state for leftovers, never a silent SUCCESS.",
        UNCLASSIFIED,
        "Keep the raw error. File it into the taxonomy corpus. Do not map it "
        "to SUCCESS or drop it.",
    ),
}


def is_actionable(entry: Mapping[str, Any] | None) -> bool:
    """A mapped message has three non-empty parts and is not a stack trace."""
    if not isinstance(entry, Mapping):
        return False
    what = str(entry.get("what_failed") or "").strip()
    why = str(entry.get("why") or "").strip()
    nxt = str(entry.get("next_command") or "").strip()
    mid = str(entry.get("message_id") or "").strip()
    if not (what and why and nxt and mid):
        return False
    if len({what, why, nxt}) < 3:
        return False
    blob = f"{what}\n{why}\n{nxt}"
    if _TRACEBACK_MARK in blob or blob.lstrip().startswith("Traceback"):
        return False
    if "python3" not in nxt and "python " not in nxt:
        # Next command must be an executable invocation, not a prose instruction.
        return False
    return True


def unmapped_classes(
    classes: Iterable[str] | None = None,
    catalog: Mapping[str, Any] | None = None,
) -> list[str]:
    """Classes in `classes` that currently have no actionable user-facing message."""
    cat = CATALOG if catalog is None else catalog
    wanted = list(CLOSED_TAXONOMY if classes is None else classes)
    return [c for c in wanted if not is_actionable(cat.get(c))]


def coverage_table(
    classes: Iterable[str] | None = None,
    catalog: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """taxonomy class, message id, next command — the evidence table."""
    cat = CATALOG if catalog is None else catalog
    wanted = list(CLOSED_TAXONOMY if classes is None else classes)
    rows = []
    for cls in wanted:
        entry = cat.get(cls) if isinstance(cat.get(cls), Mapping) else {}
        rows.append(
            {
                "taxonomy_class": cls,
                "message_id": (entry or {}).get("message_id") or None,
                "next_command": (entry or {}).get("next_command") or None,
                "mapped": is_actionable(entry),
            }
        )
    return rows


def render(taxonomy_class: str, catalog: Mapping[str, Any] | None = None) -> str:
    cat = CATALOG if catalog is None else catalog
    entry = cat.get(taxonomy_class)
    if not is_actionable(entry):
        return (
            f"TAXONOMY_CLASS: {taxonomy_class}\n"
            "MAPPED: false\n"
            "WHAT: (unmapped — no user-facing message)\n"
            "WHY: (unmapped)\n"
            "NEXT: (none)\n"
        )
    assert isinstance(entry, Mapping)
    hint = str(entry.get("hint") or "").strip()
    lines = [
        f"TAXONOMY_CLASS: {taxonomy_class}",
        f"MESSAGE_ID: {entry['message_id']}",
        "MAPPED: true",
        f"WHAT: {entry['what_failed']}",
        f"WHY: {entry['why']}",
        f"NEXT: {entry['next_command']}",
    ]
    if hint:
        lines.append(f"HINT: {hint}")
    return "\n".join(lines) + "\n"


def traceback_only_fixture() -> dict[str, str]:
    """Negative control: a bare stack trace must score as unmapped."""
    return {
        "taxonomy_class": "timeout",
        "message_id": "MSG-FAKE-TRACEBACK",
        "what_failed": "Traceback (most recent call last):\n  File 'x.py', line 1, in <module>",
        "why": "Traceback (most recent call last):",
        "next_command": next_command_for("timeout"),
    }
