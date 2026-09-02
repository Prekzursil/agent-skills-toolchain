#!/usr/bin/env python3
"""Probe 2: production reducer matches oracle; always-true stub fails the harness."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from conditions import CONDITION_IDS  # noqa: E402
from harness import (  # noqa: E402
    always_true_reducer,
    compare_candidate,
    production_reducer,
)


def main() -> int:
    prod = compare_candidate(production_reducer())
    print(
        json.dumps(
            {
                "mode": "production",
                "all_agree": prod["all_agree"],
                "mismatch_count": len(prod["mismatches"]),
                "per_condition": prod["per_condition"],
                "row_count": prod["row_count"],
            },
            indent=1,
            sort_keys=True,
        )
    )
    if not prod["all_agree"]:
        print("FAILED:TST-0001-probe2 production reducer disagrees with oracle")
        print(json.dumps(prod["mismatches"][:4], indent=1, sort_keys=True))
        return 1
    for cid in CONDITION_IDS:
        bucket = prod["per_condition"].get(cid) or {}
        if bucket.get("rows", 0) < 1 or bucket.get("agree") != bucket.get("rows"):
            print(f"FAILED:TST-0001-probe2 per-condition {cid} {bucket}")
            return 1
    pass_bucket = prod["per_condition"].get("PASS") or {}
    if pass_bucket.get("rows", 0) < 1 or pass_bucket.get("agree") != pass_bucket.get("rows"):
        print(f"FAILED:TST-0001-probe2 PASS bucket {pass_bucket}")
        return 1

    stub = compare_candidate(always_true_reducer())
    print(
        json.dumps(
            {
                "mode": "always-true",
                "all_agree": stub["all_agree"],
                "mismatch_count": len(stub["mismatches"]),
                "row_count": stub["row_count"],
            },
            indent=1,
            sort_keys=True,
        )
    )
    if stub["all_agree"]:
        print("FAILED:TST-0001-probe2 always-true reducer was accepted (harness vacuous)")
        return 1
    if len(stub["mismatches"]) < 12:
        print(
            f"FAILED:TST-0001-probe2 always-true mismatches={len(stub['mismatches'])} want>=12"
        )
        return 1
    print(
        "SUCCESS:TST-0001-probe2 reducer matches oracle per-condition; "
        "always-true stub fails the harness"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
