#!/usr/bin/env python3
"""Compare two 12-condition verdict objects. UNKNOWN vs SATISFIED is a disagreement."""
from __future__ import annotations

from typing import Any


def differ(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    lrows = {int(r["n"]): r for r in (left.get("conditions") or []) if isinstance(r, dict)}
    rrows = {int(r["n"]): r for r in (right.get("conditions") or []) if isinstance(r, dict)}
    disagreements: list[dict[str, Any]] = []
    agreements: list[dict[str, Any]] = []
    not_checked: list[int] = []
    for n in range(1, 13):
        l = lrows.get(n)
        r = rrows.get(n)
        lo = (l or {}).get("outcome")
        ro = (r or {}).get("outcome")
        row = {
            "n": n,
            "left": lo,
            "right": ro,
            "left_basis": (l or {}).get("basis"),
            "right_basis": (r or {}).get("basis"),
        }
        if l is None or r is None:
            not_checked.append(n)
            disagreements.append(row)
            continue
        if lo != ro:
            disagreements.append(row)
        else:
            agreements.append(row)
            if lo in {"UNKNOWN", "INAPPLICABLE"}:
                not_checked.append(n)
    return {
        "left_verdict": left.get("verdict"),
        "right_verdict": right.get("verdict"),
        "left_implementation": left.get("implementation"),
        "right_implementation": right.get("implementation"),
        "agreement_count": len(agreements),
        "disagreement_count": len(disagreements),
        "not_checked": not_checked,
        "disagreements": disagreements,
        "agreements": agreements,
        "verdicts_match": left.get("verdict") == right.get("verdict"),
    }
