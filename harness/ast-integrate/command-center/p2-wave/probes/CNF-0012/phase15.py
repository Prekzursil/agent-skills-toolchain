#!/usr/bin/env python3
"""Phase 15 gate census used to flag load-bearing stale confirmations."""
from __future__ import annotations

from typing import Any

ADVISORY_CLASS_GATES = frozenset({"ADV-0016"})


def phase15_units(catalog: dict) -> list[dict]:
    out = []
    for unit in catalog.get("work_units") or []:
        if isinstance(unit, dict) and str(unit.get("phase")) == "15":
            out.append(unit)
    return out


def load_bearing_flags(receipt: dict, p15: list[dict]) -> list[str]:
    """A confirmation is load-bearing when a Phase 15 gate depends on it.

    CNF-0126 recomputes promotion conditions from receipts, but that does not
    make every corpus row load-bearing by default. Only explicit citations,
    matching claim ids, and catalog dependencies count.
    """
    ids = {str(u.get("id") or "") for u in p15}
    reasons: list[str] = []
    cid = str(receipt.get("claim_id") or "")
    rid = str(receipt.get("receipt_id") or receipt.get("id") or "")
    if cid in ids:
        reasons.append(f"claim_id-is-phase15-gate:{cid}")
    if rid in ids:
        reasons.append(f"receipt_id-is-phase15-gate:{rid}")
    named = receipt.get("load_bearing_for") or []
    if isinstance(named, list):
        for gate in named:
            g = str(gate)
            if g in ids:
                reasons.append(f"receipt-names-gate:{g}")
    for unit in p15:
        uid = str(unit.get("id") or "")
        deps = unit.get("dependencies") or []
        if cid in deps or rid in deps:
            reasons.append(f"phase15-depends:{uid}")
    if receipt.get("advisory_class") and cid in ADVISORY_CLASS_GATES:
        reasons.append("advisory-class-phase15-gate")
    return reasons


def gate_summaries(p15: list[dict]) -> list[dict[str, Any]]:
    rows = []
    for unit in p15:
        uid = str(unit.get("id") or "")
        rows.append(
            {
                "id": uid,
                "title": unit.get("title"),
                "advisory_class": uid in ADVISORY_CLASS_GATES,
                "consumes_receipts": "receipt"
                in " ".join(str(x) for x in (unit.get("inputs") or [])).lower()
                or "confirmation" in " ".join(str(x) for x in (unit.get("inputs") or [])).lower(),
            }
        )
    return rows
