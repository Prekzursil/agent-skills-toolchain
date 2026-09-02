#!/usr/bin/env python3
"""Probe 1: four catalog controls + both-states on the planted unused key.

Re-runs the detector against fixtures/product (not the receipt bytes). Also
checks the live artifact recorded those controls as PASS when present.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import config_orphan as C  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0005.json"
FIXTURE = HERE / "fixtures" / "product"
REQUIRED = (
    "planted-orphan",
    "planted-undeclared",
    "fixture-only",
    "negative-matched",
)


def main() -> int:
    if not FIXTURE.is_dir():
        print("FAILED:BLD-0005-probe1 fixture tree missing")
        return 1
    ctrl = C.run_controls(FIXTURE)
    for t in ctrl["tests"]:
        print(f"control {t['id']} result={t['result']} key={t.get('key')}")
    if not ctrl["pass"]:
        print("FAILED:BLD-0005-probe1 a planted control did not fire or did not go silent")
        print(json.dumps(ctrl["tests"], indent=2))
        return 1
    missing_reviewer = [k for k in C.REVIEWER_ORPHANS if k not in ctrl["reviewer_orphan_keys"]]
    if missing_reviewer:
        print(f"FAILED:BLD-0005-probe1 reviewer orphan keys missing {missing_reviewer}")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:BLD-0005-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "BLD-0005":
        print("FAILED:BLD-0005-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:BLD-0005" not in json.dumps(doc):
        print("FAILED:BLD-0005-probe1 sentinel absent")
        return 1
    recorded = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for rid in REQUIRED:
        row = recorded.get(rid)
        if not row or row.get("result") != "PASS":
            print(f"FAILED:BLD-0005-probe1 receipt test {rid} not PASS")
            return 1
    print(
        f"fixture orphans={ctrl['matrix_counts']['only_left']} "
        f"undeclared={ctrl['matrix_counts']['only_right']} "
        f"fixture_only={ctrl['matrix_counts']['fixture_only']} "
        f"matched={ctrl['matrix_counts']['matched']}"
    )
    print("SUCCESS:BLD-0005-probe1 planted controls and both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
