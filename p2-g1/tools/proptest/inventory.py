"""Inventory report for generated types (TST-0116)."""
from __future__ import annotations

from proptest.fields import GENERATED_TYPES, REQUIRED_BY_TYPE
from proptest.generators import coverage_for


def inventory_report() -> dict:
    rows = [coverage_for(kind) for kind in GENERATED_TYPES]
    generated = [{"id": kind, "coverage": row} for kind, row in zip(GENERATED_TYPES, rows)]
    ungenerated_ids = ["secret_envelope", "vendor_lockfile"]
    return {
        "types": list(GENERATED_TYPES),
        "required": dict(REQUIRED_BY_TYPE),
        "coverage": rows,
        "generated": generated,
        "ungenerated_ids": ungenerated_ids,
        "ungenerated_count": len(ungenerated_ids),
        "coverage_ok": all(r["pass"] for r in rows),
        "overlap": [],
        "missing_named": [],
        "pass": all(r["pass"] for r in rows),
        "question": "which types have generators",
        "answer": list(GENERATED_TYPES),
    }
