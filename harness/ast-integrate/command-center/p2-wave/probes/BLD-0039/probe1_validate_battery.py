#!/usr/bin/env python3
"""Probe 1: 16-mutation control set against validate.py must be 15/16.

Re-runs the battery live. Also checks the receipt records a KILLED mutation
(rate, not survivors-only) and the V-FIELDS defaults-deleted survivor.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import battery as B  # noqa: E402
from isolate import REPO  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0039.json"
SENTINEL = "SUCCESS:BLD-0039"


def _view(doc: dict) -> dict:
    """Merge report payload so census fields may live under report (receipt_core)."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    view = dict(report)
    view.update({k: v for k, v in doc.items() if k != "report"})
    return view


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 2048:
        print("FAILED:BLD-0039-probe1 receipt missing or thin")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:BLD-0039-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if doc.get("unit_id") != "BLD-0039":
        print("FAILED:BLD-0039-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:BLD-0039-probe1 self-declared", doc.get("state"))
        return 1

    result = B.run_control_set()
    errs = B.assert_control_green(result)
    print(
        json.dumps(
            {
                "n": result["n"],
                "killed": result["killed"],
                "survived": result["survived"],
                "firing_rate": result["firing_rate"],
                "survivor_ids": result["survivor_ids"],
                "clean_baseline_exit": result["clean_baseline_exit"],
                "shared_tree_unchanged": result["isolation"]["shared_tree_unchanged"],
                "m01_killed": any(
                    r["id"] == "M01-REACH-1-dangling" and r["verdict"] == "KILLED"
                    for r in result["rows"]
                ),
            },
            sort_keys=True,
        )
    )
    if errs:
        print("FAILED:BLD-0039-probe1", "; ".join(errs))
        return 1

    view = _view(doc)
    claimed = view.get("control_set") or {}
    if claimed.get("firing_rate") != result["firing_rate"]:
        print(
            "FAILED:BLD-0039-probe1 receipt firing_rate "
            f"{claimed.get('firing_rate')} != live {result['firing_rate']}"
        )
        return 1
    if claimed.get("survivor_id") != "M16-V-FIELDS-defaults-deleted":
        print("FAILED:BLD-0039-probe1 receipt survivor_id mismatch")
        return 1
    killed_in_receipt = [
        m
        for m in (view.get("mutations") or [])
        if isinstance(m, dict) and m.get("verdict") == "KILLED"
    ]
    if not killed_in_receipt:
        print("FAILED:BLD-0039-probe1 receipt records no KILLED mutation (rate missing)")
        return 1
    print(
        f"rate={result['firing_rate']} survivor={result['survivor_ids'][0]} "
        f"killed_recorded={len(killed_in_receipt)}"
    )
    print("SUCCESS:BLD-0039-probe1 15-of-16 validate.py battery")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
