#!/usr/bin/env python3
"""Probe 1: 3/3 registered adapters pass the shared five-check suite.

Both-states: the inexpressible / injection / unsafe twins are inside the suite.
A 2-adapter slice must not satisfy all_pass (count floor is 3).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from workflow_import.harness.suite import CHECKS, run_all  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0163.json"


def main() -> int:
    result = run_all()
    printable = {
        "adapter_count": result["adapter_count"],
        "registered_ids": result["registered_ids"],
        "passed_ids": result["passed_ids"],
        "pass_count": result["pass_count"],
        "all_pass": result["all_pass"],
        "checks": result["checks"],
        "per_adapter": {
            aid: {
                "pass": row["pass"],
                "checks": {k: v["pass"] for k, v in row["checks"].items()},
                "extras_pass": row["extras"].get("pass"),
            }
            for aid, row in result["adapters"].items()
        },
    }
    print(json.dumps(printable, sort_keys=True))
    if not result["all_pass"]:
        print("FAILED:IMP-0163-probe1 suite not 3/3")
        for aid, row in result["adapters"].items():
            if not row["pass"]:
                print(f"  {aid}: {json.dumps(row, default=str)[:1500]}")
        return 1
    if result["adapter_count"] != 3 or result["pass_count"] != 3:
        print(
            f"FAILED:IMP-0163-probe1 count floor "
            f"adapters={result['adapter_count']} pass={result['pass_count']}"
        )
        return 1
    if tuple(result["checks"]) != CHECKS:
        print(f"FAILED:IMP-0163-probe1 checks drifted {result['checks']}")
        return 1
    two = result["passed_ids"][:2]
    if len(two) == 3:
        print("FAILED:IMP-0163-probe1 2-adapter slice collapsed to 3")
        return 1
    if not ART.is_file():
        print("FAILED:IMP-0163-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0163-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0163" not in text:
        print("FAILED:IMP-0163-probe1 sentinel-absent")
        return 1
    live_ids = list(result["registered_ids"])
    art_ids = list((doc.get("conformance") or {}).get("registered_ids") or [])
    if art_ids != live_ids:
        print(f"FAILED:IMP-0163-probe1 receipt ids {art_ids} != live {live_ids}")
        return 1
    if (doc.get("conformance") or {}).get("pass_count") != 3:
        print("FAILED:IMP-0163-probe1 receipt pass_count != 3")
        return 1
    print("3/3 adapters pass shared suite; 2-adapter slice is not 3")
    print("SUCCESS:IMP-0163-probe1 shared-suite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
