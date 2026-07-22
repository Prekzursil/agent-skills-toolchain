"""Completeness gate for fan-out artifacts.

A unit's exit code is NOT proof it produced anything. Blocking on process exit says only that the
process ended; the artifact may be absent, truncated, or unparsable. This module is the AND-gate
that decides whether a unit actually delivered.

DESIGN NOTE — why there is no byte floor by default
---------------------------------------------------
The obvious gate is `len(artifact) >= N`. It is wrong, and it failed in production: a 127-unit
audit ran two lanes, one contractually terse (a fenced verdict block plus one reason line, median
382 B) and one verbose (median 1690 B). An 800-byte floor rejected 84 of 85 VALID artifacts in the
terse lane and 0 of 42 in the verbose lane.

The tell generalises: **a gate that fails one entire lane and no part of another is measuring
verbosity, not truncation.** So the default gate is STRUCTURAL — sentinel present in the tail, plus
every field the lane's contract requires. That detects a truncated artifact by what is missing from
it rather than by how short it is, and it cannot be fooled by a long-but-malformed file.

A byte floor remains available as `min_bytes` for callers whose contract genuinely fixes a size,
but it is opt-in and must be justified per lane, never applied globally.
"""

from __future__ import annotations

import pathlib
import re
import sys
from dataclasses import dataclass, field

# The size/sentinel rule belongs to the C1 shared completion predicate, which states it is "the
# single definition every producer and consumer must share". This module therefore DELEGATES that
# half rather than reimplementing it, and adds only what C1 does not cover: unit identity and the
# fenced-field contract.
#
# This import is also the point of the exercise. C1 was measured INERT — present, tested by itself,
# with ZERO production callers — and the reason turned out to be an API mismatch, not neglect:
# `artifact_ok` is path-based, while every real consumer here has TEXT harvested from object
# storage. A path-only predicate silently pushes each consumer into writing its own copy, which is
# exactly how a shared definition acquires no adopters. `artifact_text_ok` closes that gap and this
# is its first production caller.
_SHARED = pathlib.Path(__file__).resolve().parents[2] / "hooks" / "_shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))
try:
    from completion import artifact_text_ok
except Exception:  # pragma: no cover - exercised by the fallback test
    artifact_text_ok = None  # type: ignore[assignment]

SENTINEL_TAIL_BYTES = 600
"""How far from the end the completion sentinel must appear.

Measured in bytes, not lines: agents append trailing prose of unpredictable line length, and a
line-based window silently widens on a file with long lines.
"""


@dataclass(frozen=True)
class GateResult:
    """Terminal state for one artifact. `ok` is the only thing callers should branch on."""

    ok: bool
    reason: str
    fields: dict[str, str] = field(default_factory=dict)

    def __bool__(self) -> bool:  # so `if gate(...):` reads naturally
        return self.ok


def parse_block(text: str, fence: str) -> dict[str, str] | None:
    """Extract a ```<fence> ... ``` block as key: value pairs, or None if absent/empty.

    Parses the FIELD, never the document. Searching the whole artifact for a token matches prose
    that merely discusses the token — the use-vs-mention error, which recurred three separate times
    in one program (a stub ledger scoring 0 of 9 real, a platform classifier misreading 6 of 9
    options, and a fold census inflating 10 findings to 13). Every one was a document-wide grep
    where a field read was meant.
    """
    m = re.search(rf"```{re.escape(fence)}\s*(.+?)```", text, re.S)
    if not m:
        return None
    out: dict[str, str] = {}
    for line in m.group(1).strip().splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out or None


def gate(
    text: str,
    unit_id: str,
    *,
    fence: str | None = None,
    required_fields: tuple[str, ...] = (),
    min_bytes: int = 0,
) -> GateResult:
    """Decide whether one artifact is complete.

    `unit_id` must appear in the sentinel so a unit cannot be credited with a sibling's artifact —
    a harvest that globs a results directory will otherwise happily accept a duplicate.
    """
    # Size + sentinel are C1's rule, not ours. min_bytes=0 by default — see the byte-floor note.
    if artifact_text_ok is not None:
        ok, why = artifact_text_ok(
            text,
            sentinel="UNIT-COMPLETE",
            min_bytes=min_bytes,
            sentinel_tail=SENTINEL_TAIL_BYTES,
        )
        if not ok:
            return GateResult(False, why)
    else:  # C1 unavailable — degrade to a local equivalent rather than passing everything
        raw = text.encode("utf-8", errors="replace")
        if min_bytes and len(raw) < min_bytes:
            return GateResult(
                False, f"below explicit min_bytes ({len(raw)} < {min_bytes})"
            )
        if "UNIT-COMPLETE" not in raw[-SENTINEL_TAIL_BYTES:].decode(
            "utf-8", errors="replace"
        ):
            return GateResult(False, "no completion sentinel in tail")

    # Unit IDENTITY is this module's own concern: C1 answers "is an artifact complete", not
    # "is it THIS unit's artifact". A directory harvest without it credits a unit with a sibling's.
    raw = text.encode("utf-8", errors="replace")
    tail = raw[-SENTINEL_TAIL_BYTES:].decode("utf-8", errors="replace")
    if unit_id and unit_id not in tail:
        return GateResult(False, f"sentinel does not name this unit ({unit_id})")

    fields: dict[str, str] = {}
    if fence is not None:
        parsed = parse_block(text, fence)
        if parsed is None:
            return GateResult(False, f"no parsable ```{fence} block")
        fields = parsed
        missing = [k for k in required_fields if not fields.get(k)]
        if missing:
            return GateResult(False, f"missing required field(s): {missing}", fields)

    return GateResult(True, "ok", fields)
