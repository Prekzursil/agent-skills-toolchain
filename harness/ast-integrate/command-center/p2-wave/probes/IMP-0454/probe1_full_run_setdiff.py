#!/usr/bin/env python3
"""Probe 1: after a full writer run the disk-vs-manifest set difference is empty.

Two mechanically independent signals:
  (1) registering_writer.reconcile
  (2) scenario.independent_setdiff (separate rglob + json.load)
Registration is observed by re-reading the manifest after each emit, before
any reconcile call — so a later sweep is not what produced the rows.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import UNIT, run_full_writer_run  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0454.json"
SENTINEL = "SENTINEL:IMP-0454:MANIFEST-AUTO-REGISTERED"


def check_receipt() -> str:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "receipt-missing"
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return "receipt-unparseable"
    if not isinstance(doc, dict):
        return "receipt-not-object"
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{st}"
    if SENTINEL not in text:
        return "sentinel-absent"
    if doc.get("unregistered_count_after_full_run") not in (0, "0"):
        return "receipt-unregistered-count-not-zero"
    return "ok"


def main() -> int:
    result = run_full_writer_run()
    receipt = check_receipt()
    payload = {
        "probe": "probe1-full-run-setdiff",
        "unit_id": UNIT,
        "unregistered_count": result["unregistered_count"],
        "set_difference_empty": result["set_difference_empty"],
        "agree": result["agree"],
        "registered_at_emit_not_sweep": result["registered_at_emit_not_sweep"],
        "reconcile_is_read_only": result["reconcile_is_read_only"],
        "library_unregistered": result["library_reconcile"]["unregistered"],
        "independent_unregistered": result["independent_setdiff"]["unregistered"],
        "emitted": result["emitted"],
        "receipt": receipt,
        "pass": (
            result["set_difference_empty"]
            and result["agree"]
            and result["registered_at_emit_not_sweep"]
            and result["reconcile_is_read_only"]
            and result["unregistered_count"] == 0
            and receipt == "ok"
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not result["set_difference_empty"] or result["unregistered_count"] != 0:
        print("FAILED:IMP-0454-probe1 full-run set difference is not empty")
        return 1
    if not result["agree"]:
        print("FAILED:IMP-0454-probe1 library and independent walkers disagree")
        return 1
    if not result["registered_at_emit_not_sweep"]:
        print("FAILED:IMP-0454-probe1 row missing from disk manifest immediately after emit")
        return 1
    if not result["reconcile_is_read_only"]:
        print("FAILED:IMP-0454-probe1 reconcile mutated the manifest")
        return 1
    if receipt != "ok":
        print(f"FAILED:IMP-0454-probe1 receipt {receipt}")
        return 1
    print(
        f"unregistered_count={result['unregistered_count']} "
        f"set_difference_empty={result['set_difference_empty']} "
        f"emit_time={result['registered_at_emit_not_sweep']}"
    )
    print("SUCCESS:IMP-0454-probe1 full-run disk-vs-manifest set difference is empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
