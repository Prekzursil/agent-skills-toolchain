#!/usr/bin/env python3
"""Named probe 1: both-states, two known-broken directions, sentinel format."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0168.json"


def main() -> int:
    ctrl = A.run_controls()
    checks = [
        ("healthy_silent", ctrl.get("healthy_silent")),
        ("direction_a_fires_on_truncate", ctrl.get("direction_a_fires_on_truncate")),
        ("direction_b_fires_on_complete_without_sentinel", ctrl.get("direction_b_fires_on_complete_without_sentinel")),
        ("near_miss_does_not_count", ctrl.get("near_miss_does_not_count")),
        ("pass", ctrl.get("pass")),
    ]
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:CNF-0168-probe1 {name}")
            print(json.dumps(ctrl, indent=2, default=str)[:4000])
            return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0168-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in A.NOT_DELIVERING:
        print(f"FAILED:CNF-0168-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CNF-0168" not in text:
        print("FAILED:CNF-0168-probe1 sentinel absent")
        return 1
    if not A.token_present(text, "SUCCESS:CNF-0168"):
        print("FAILED:CNF-0168-probe1 SUCCESS:CNF-0168 is not an exact token")
        return 1
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in (
        "T-truncate-sentinel",
        "T-complete-without-sentinel",
        "T-healthy-silent",
        "T-sentinel-format",
    ):
        row = tests.get(tid)
        if not row or row.get("result") != "PASS":
            print(f"FAILED:CNF-0168-probe1 artifact test {tid} not PASS")
            return 1
    dirs = A.directions_of(doc)
    if "combined_count" in dirs or "sentinel_mismatch" in dirs:
        print("FAILED:CNF-0168-probe1 combined mismatch number present")
        return 1
    if "combined_count" in doc or "sentinel_mismatch" in doc:
        print("FAILED:CNF-0168-probe1 combined mismatch number present at root")
        return 1
    a = dirs.get("sentinel_on_incomplete") or {}
    b = dirs.get("complete_without_sentinel") or {}
    if not isinstance(a.get("count"), int) or not isinstance(b.get("count"), int):
        print("FAILED:CNF-0168-probe1 directions missing separate counts")
        return 1
    if "ids" not in a or "ids" not in b:
        print("FAILED:CNF-0168-probe1 directions missing ids")
        return 1
    print(
        f"live_A={a['count']} live_B={b['count']} "
        f"near_misses={len(ctrl.get('near_misses') or [])}"
    )
    print("SUCCESS:CNF-0168-probe1 both-states two-directions sentinel-format")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
