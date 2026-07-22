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

import re
from dataclasses import dataclass, field

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
    raw = text.encode("utf-8", errors="replace")
    if min_bytes and len(raw) < min_bytes:
        return GateResult(False, f"below explicit min_bytes ({len(raw)} < {min_bytes})")

    tail = raw[-SENTINEL_TAIL_BYTES:].decode("utf-8", errors="replace")
    if "UNIT-COMPLETE" not in tail:
        return GateResult(False, "no completion sentinel in tail")
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
