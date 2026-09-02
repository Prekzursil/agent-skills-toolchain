#!/usr/bin/env python3
"""Probe 2: exit 127 is TOOL-FAILURE; local ruff gate is not in the inventory."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from classify import classify_scanner_exit  # noqa: E402
from inventory import LOCAL_CONTROL_GATE, build_inventory  # noqa: E402
from scanner import classify_missing_scanner  # noqa: E402


def main() -> int:
    if classify_scanner_exit(127) != "TOOL-FAILURE":
        print("FAILED:BLD-0046-probe2 127 did not classify TOOL-FAILURE")
        return 1
    if classify_scanner_exit(0) != "CLEAN":
        print("FAILED:BLD-0046-probe2 exit 0 must remain CLEAN")
        return 1
    if classify_scanner_exit(1) != "FINDINGS":
        print("FAILED:BLD-0046-probe2 exit 1 must remain FINDINGS")
        return 1
    miss = classify_missing_scanner()
    if not miss["pass"]:
        print("FAILED:BLD-0046-probe2 missing scanner", json.dumps(miss))
        return 1
    inv = build_inventory({})
    ids = [e["gate_id"] for e in inv["entries"]]
    if LOCAL_CONTROL_GATE in ids:
        print(f"FAILED:BLD-0046-probe2 {LOCAL_CONTROL_GATE} listed in inventory")
        return 1
    if any("lint" in i and "quality" in i for i in ids):
        print("FAILED:BLD-0046-probe2 quality lint gate leaked into inventory", ids)
        return 1
    undated = [e for e in inv["entries"] if e["classification"] == "UNDATED-GREEN"]
    if not undated or undated[0]["treated_as"] != "UNKNOWN":
        print("FAILED:BLD-0046-probe2 undated green not treated UNKNOWN")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe2-controls",
                "unit_id": "BLD-0046",
                "exit_127": miss,
                "local_gate": LOCAL_CONTROL_GATE,
                "local_gate_in_inventory": False,
                "undated_treated_as": "UNKNOWN",
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"exit_127={miss['exit_code']} class={miss['classification']} "
        f"excluded={LOCAL_CONTROL_GATE} undated={undated[0]['gate_id']}"
    )
    print("SUCCESS:BLD-0046-probe2 TOOL-FAILURE and local-gate exclusion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
