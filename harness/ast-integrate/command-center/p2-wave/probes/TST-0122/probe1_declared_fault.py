#!/usr/bin/env python3
"""Named probe 1: each shipped primitive produces its declared fault."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from chaos.session import SHIPPED, run_declared_faults  # noqa: E402
from schema_local import domain  # noqa: E402

UNIT = "TST-0122"
ART = REPO / "command-center" / "receipts" / "TST-0122.json"
SEED = 122


def fail(msg: str) -> int:
    print(f"FAILED:TST-0122-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(receipt)
    if "SUCCESS:TST-0122" not in text:
        return fail("sentinel absent")
    if str(receipt.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {receipt.get('state')}")
    payload = domain(receipt)
    if payload.get("scratch_only") is not True:
        return fail("scratch_only is not true")
    if payload.get("host_clock_mutated") is not False:
        return fail("host clock must not be mutated")

    report = run_declared_faults(SEED)
    missing = [r for r in report["results"] if not r.get("observed")]
    if missing:
        return fail(f"undeclared-or-unobserved {missing}")
    if report["count"] != len(SHIPPED):
        return fail(f"count {report['count']} != {len(SHIPPED)}")

    shipped_ids = {p["id"] for p in payload.get("primitives") or [] if p.get("shipped")}
    if shipped_ids != set(SHIPPED):
        return fail(f"receipt shipped set mismatch {shipped_ids} vs {set(SHIPPED)}")

    payload = {
        "all_observed": True,
        "count": report["count"],
        "ids": [r["id"] for r in report["results"]],
        "pass": True,
        "probe": "probe1-declared-fault",
        "seed": SEED,
        "unit_id": UNIT,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:TST-0122-probe1 each shipped primitive produced its declared fault")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
