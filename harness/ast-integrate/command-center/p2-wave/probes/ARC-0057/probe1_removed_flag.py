#!/usr/bin/env python3
"""Probe 1: deleting a documented flag from the implementation turns the doc test red."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import doc_test as D  # noqa: E402

ART = REPO / "command-center/phase3/A8/TEST-PLAN.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0057-probe1 TEST-PLAN.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "ARC-0057":
        print("FAILED:ARC-0057-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:ARC-0057" not in json.dumps(doc):
        print("FAILED:ARC-0057-probe1 sentinel absent")
        return 1

    live = D.mutation_control()
    print(json.dumps({"probe": "removed-flag", **live}, sort_keys=True))
    if not live.get("clean_pass"):
        print("FAILED:ARC-0057-probe1 clean documented --format command did not pass")
        return 1
    if not live.get("mutant_doc_test_red"):
        print("FAILED:ARC-0057-probe1 mutant still green after deleting --format")
        return 1
    payload = D.plan_payload(doc)
    recorded = payload.get("mutation_control") or {}
    if recorded.get("mutant_doc_test_red") is not True:
        print("FAILED:ARC-0057-probe1 artifact mutation_control not red")
        return 1
    if recorded.get("documented_flag") != live.get("documented_flag"):
        print("FAILED:ARC-0057-probe1 flag drift vs artifact")
        return 1
    print("SUCCESS:ARC-0057-probe1 removed-flag mutation went red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
