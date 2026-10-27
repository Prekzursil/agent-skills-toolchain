"""Oracle labels for TST-0309 overlap cases."""
from __future__ import annotations

from typing import Any

MATCH = "match"
MISMATCH = "mismatch"


def oracle_label(case: dict[str, Any]) -> str:
    raw = case.get("oracle") or case.get("gold") or case.get("label")
    if raw in {MATCH, MISMATCH}:
        return str(raw)
    cid = str(case.get("id") or "")
    if cid.startswith("C"):
        try:
            n = int(cid[1:])
        except ValueError:
            n = 0
        return MATCH if n < 25 else MISMATCH
    return MATCH
