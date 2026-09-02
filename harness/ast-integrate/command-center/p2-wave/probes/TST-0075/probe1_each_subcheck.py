#!/usr/bin/env python3
"""Probe 1: each sub-check fires on its own breakage; aggregate GREEN needs all.

Re-runs the both-states pair for every health sub-check against a known-good
install and that sub-check's seeded breakage. A GREEN aggregate on any
breakage, or a sub-check silent in both states, fails this probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as HV  # noqa: E402
import health as H  # noqa: E402

ART = REPO / "command-center/receipts/TST-0075.json"


def main() -> int:
    live = HV.evaluate_live()
    errors = HV.assertions(live)
    payload = {
        "probe": "probe1-each-subcheck",
        "unit_id": "TST-0075",
        "good_aggregate": live["good_aggregate"],
        "pairs": [
            {
                "id": r["id"],
                "trusted": r["trusted"],
                "good": r["good"]["verdict"],
                "broken": r["broken"]["verdict"] if r["broken"] else None,
                "breakage_green": r["breakage_green"],
                "only_target_failed": (r.get("specificity") or {}).get(
                    "only_target_failed"
                ),
            }
            for r in live["pairs"]
        ],
        "errors": errors,
        "pass": not errors,
    }
    print(json.dumps(payload, sort_keys=True))
    n = len(live["pairs"])
    trusted = sum(1 for r in live["pairs"] if r["trusted"])
    print(
        f"good={live['good_aggregate']} pairs={n} trusted={trusted} "
        f"errors={len(errors)}"
    )
    if errors:
        for e in errors:
            print(f"FAILED:TST-0075-probe1 {e}")
        return 1
    if n != len(H.SUBCHECK_IDS) or trusted != n:
        print("FAILED:TST-0075-probe1 incomplete both-states coverage")
        return 1
    if live["good_aggregate"] != H.GREEN:
        print("FAILED:TST-0075-probe1 good install is not GREEN")
        return 1
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:TST-0075" not in text:
            print("FAILED:TST-0075-probe1 artifact sentinel absent")
            return 1
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:TST-0075-probe1 artifact self-declared {st}")
            return 1
    print("SUCCESS:TST-0075-probe1 each sub-check both-states and aggregate gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
