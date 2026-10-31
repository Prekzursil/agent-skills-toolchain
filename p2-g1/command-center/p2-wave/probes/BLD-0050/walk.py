# Recreated 2026-10-25 (wave-2 shard 7) after the original probe tree was
# lost with the prior builder session; content follows the recorded role in
# the unit receipt (anchors re-resolve live). Prior reviewer closure kept.
"""Instrument for BLD-0050: the trust-boundary walk row walker. Reads the
delivered census rows and classifies each by check_status; the completeness
probe uses it to recompute the counts block mechanically."""
from __future__ import annotations

from typing import Any

STATUSES = ("CHECKED", "UNCHECKED", "CONSUMED")


def classify(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {s: 0 for s in STATUSES}
    for r in rows:
        st = str(r.get("check_status") or "").upper()
        counts[st] = counts.get(st, 0) + 1
    return counts


def ids(rows: list[dict[str, Any]]) -> list[str]:
    return [str(r.get("id")) for r in rows]
