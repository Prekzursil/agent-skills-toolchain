#!/usr/bin/env python3
"""Probe 1: planted oracle-strength controls.

1. assert result is not None grades NO-CRASH-ONLY.
2. assert compute_score([1,2,3]) == 6 grades EXACT-VALUE (no false downgrade).
3. snapshot whose golden is regenerated from produce_report is self-confirming.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import grade as G  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "BLD-0040.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0040-probe1 {msg}")
    return 1


def by_name(rows: list[dict], name: str) -> dict | None:
    for row in rows:
        if row.get("name") == name:
            return row
    return None


def main() -> int:
    oracle_rows = G.grade_file(HERE / "fixtures" / "test_oracles.py", REPO)
    snap_rows = G.grade_file(
        HERE / "fixtures" / "snapshot" / "test_snapshot.py", REPO
    )
    no_crash = by_name(oracle_rows, "test_no_crash_only")
    exact = by_name(oracle_rows, "test_exact_value")
    snap = by_name(snap_rows, "test_snapshot_self_confirming")
    print(
        json.dumps(
            {"no_crash": no_crash, "exact": exact, "snapshot": snap},
            indent=2,
        )
    )
    if not no_crash:
        return fail("test_no_crash_only missing")
    if no_crash.get("effective_oracle") != "NO-CRASH-ONLY":
        return fail(
            f"not-None graded {no_crash.get('effective_oracle')} not NO-CRASH-ONLY"
        )
    if not exact:
        return fail("test_exact_value missing")
    if exact.get("effective_oracle") != "EXACT-VALUE":
        return fail(
            f"exact computed value graded {exact.get('effective_oracle')} not EXACT-VALUE"
        )
    if not snap:
        return fail("test_snapshot_self_confirming missing")
    if not snap.get("self_confirming"):
        return fail("self-confirming snapshot not flagged")
    if snap.get("effective_oracle") != "NO-ORACLE":
        return fail(
            f"self-confirming snapshot effective={snap.get('effective_oracle')} not NO-ORACLE"
        )

    if not RECEIPT.is_file():
        return fail("receipt absent")
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    names = {
        str(g.get("name")): g
        for g in (doc.get("grades") or [])
        if isinstance(g, dict)
    }
    rec_nc = names.get("test_no_crash_only") or {}
    rec_ex = names.get("test_exact_value") or {}
    rec_sn = names.get("test_snapshot_self_confirming") or {}
    if rec_nc.get("effective_oracle") != "NO-CRASH-ONLY":
        return fail("receipt missing NO-CRASH-ONLY control")
    if rec_ex.get("effective_oracle") != "EXACT-VALUE":
        return fail("receipt missing EXACT-VALUE control")
    if not rec_sn.get("self_confirming"):
        return fail("receipt snapshot not self-confirming")
    if "SUCCESS:BLD-0040" not in RECEIPT.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    print(
        "no_crash=NO-CRASH-ONLY exact=EXACT-VALUE "
        "snapshot=self-confirming/NO-ORACLE"
    )
    print("SUCCESS:BLD-0040-probe1 planted oracle controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
