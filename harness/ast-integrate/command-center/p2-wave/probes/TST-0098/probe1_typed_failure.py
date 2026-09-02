#!/usr/bin/env python3
"""Probe 1: every in-scope boundary x fault cell is a typed failure.

Also checks the planted empty-success swallower is detected (detector control)
and that the catalog receipt records the live matrix without EMPTY_SUCCESS
in production cells.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / "command-center/receipts/TST-0098.json"


def main() -> int:
    cells = H.run_matrix(HERE / "runtime" / "probe1")
    ok, why = H.matrix_ok(cells)
    swallow = H.run_swallower_control(HERE / "runtime" / "probe1-swallow")
    healthy = H.run_healthy(HERE / "runtime" / "probe1-healthy")
    print(
        json.dumps(
            {
                "n_cells": len(cells),
                "matrix_ok": ok,
                "why": why,
                "swallower_classification": swallow["classification"],
                "swallower_empty_success": swallow["empty_success"],
                "healthy": [c["classification"] for c in healthy],
            },
            sort_keys=True,
        )
    )
    if not ok:
        print(f"FAILED:TST-0098-probe1 matrix {why}")
        for c in cells:
            if c["classification"] != H.TYPED[c["fault"]] or c["empty_success"]:
                print(c)
        return 1
    if swallow["classification"] != "EMPTY_SUCCESS" or not swallow["empty_success"]:
        print("FAILED:TST-0098-probe1 planted swallower not detected as EMPTY_SUCCESS")
        return 1
    if any(c["classification"] != "SUCCESS" or not c["ok"] for c in healthy):
        print("FAILED:TST-0098-probe1 healthy both-state did not succeed")
        return 1
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:TST-0098-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0098-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:TST-0098" not in ART.read_text(encoding="utf-8"):
        print("FAILED:TST-0098-probe1 sentinel absent")
        return 1
    rec_cells = ((doc.get("matrix") or {}).get("cells")) or []
    if len(rec_cells) != len(H.BOUNDARIES) * len(H.FAULTS):
        print(f"FAILED:TST-0098-probe1 receipt cells {len(rec_cells)}")
        return 1
    live_by = {(c["boundary"], c["fault"]): c["classification"] for c in cells}
    for rc in rec_cells:
        key = (rc["boundary"], rc["fault"])
        if rc.get("empty_success") is True:
            print(f"FAILED:TST-0098-probe1 receipt empty_success {key}")
            return 1
        if live_by.get(key) != rc.get("classification"):
            print(
                f"FAILED:TST-0098-probe1 receipt/live mismatch {key} "
                f"live={live_by.get(key)} rec={rc.get('classification')}"
            )
            return 1
    if (doc.get("empty_success_cells") or []) != []:
        print("FAILED:TST-0098-probe1 production empty_success_cells not empty")
        return 1
    print("SUCCESS:TST-0098-probe1 typed-failure matrix + swallower detector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
