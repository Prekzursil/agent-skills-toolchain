#!/usr/bin/env python3
"""Named probe 1: linter flags Name/name; clean manifest passes in the same run.

Signal 1 of IMP-0009. Negative control is both-states in one process: planted
fixture must produce a case-distinct finding and the clean fixture must not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import case_collision as cc  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0009.json"
FIX = REPO / "tools" / "plugin" / "tests" / "fixtures"
CLEAN = FIX / "clean-manifest.json"
PLANTED = FIX / "name-collision.json"
DUP = FIX / "duplicate-keys.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0009-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0009-probe1 receipt unparseable {exc}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:IMP-0009-probe1 receipt not an object")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0009-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0009" not in text:
        print("FAILED:IMP-0009-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != "IMP-0009":
        print(f"FAILED:IMP-0009-probe1 unit_id {doc.get('unit_id')}")
        return 1

    clean = cc.lint_file(CLEAN)
    planted = cc.lint_file(PLANTED)
    dup = cc.lint_file(DUP)
    if not clean["parse_ok"] or clean["findings"]:
        print("FAILED:IMP-0009-probe1 clean fixture did not pass")
        print(json.dumps(clean, indent=2)[:2000])
        return 1
    case_hits = [f for f in planted.get("findings") or [] if f["kind"] == cc.KIND_CASE]
    if not planted["parse_ok"] or not case_hits:
        print("FAILED:IMP-0009-probe1 planted Name/name was not flagged")
        print(json.dumps(planted, indent=2)[:2000])
        return 1
    keys = set(case_hits[0]["keys"])
    if keys != {"Name", "name"}:
        print(f"FAILED:IMP-0009-probe1 expected Name/name got {keys}")
        return 1
    dup_hits = [f for f in dup.get("findings") or [] if f["kind"] == cc.KIND_DUP]
    if not dup["parse_ok"] or not dup_hits:
        print("FAILED:IMP-0009-probe1 exact duplicate was not flagged")
        return 1

    payload = {
        "adjudicated": True,
        "clean_findings": 0,
        "planted_case_distinct": True,
        "planted_keys": sorted(keys),
        "duplicate_rejected": True,
        "negative_control_same_run": True,
        "pass": True,
        "probe": "probe1-linter-flags",
        "unit_id": "IMP-0009",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "clean_ok=True planted_flagged=True duplicate_flagged=True "
        "same_run_negative_control=True"
    )
    print("SUCCESS:IMP-0009-probe1 linter flags Name/name and clean passes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
