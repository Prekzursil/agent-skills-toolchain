#!/usr/bin/env python3
"""Probe 2: ledger resolution before unbacked; planted failed-run contradiction."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from controls import (  # noqa: E402
    test_contradiction_planted_failed_run_is_caught,
    test_resolution_attempted_against_ledger_before_unbacked,
)


def main() -> int:
    resolve = test_resolution_attempted_against_ledger_before_unbacked()
    contra = test_contradiction_planted_failed_run_is_caught()
    payload = {
        "probe": "probe2-resolve-and-contradiction",
        "unit_id": "TST-0351",
        "pass": bool(resolve["pass"] and contra["pass"]),
        "test_resolution_attempted_against_ledger_before_unbacked": resolve["pass"],
        "test_contradiction_planted_failed_run_is_caught": contra["pass"],
        "both_states": resolve.get("both_states"),
        "live_run_id": resolve.get("live_run_id"),
        "contradicted_run_id": contra.get("run_id"),
        "first_class": contra.get("first_class"),
        "contradiction_reason": contra.get("reason"),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:TST-0351-probe2 resolution-before-unbacked or contradiction")
        return 1
    print(
        "SUCCESS:TST-0351-probe2 ledger-read-resolves="
        f"{(resolve.get('both_states') or {}).get('ledger_read_resolves')} "
        f"contradicted={contra.get('run_id')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
