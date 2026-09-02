#!/usr/bin/env python3
"""Probe 1: planted-wrong consensus is overturned; 20-run change rate is measured."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import measure  # noqa: E402


def main() -> int:
    m = measure()
    planted = m["canonical"]["planted_wrong"]
    rate = m["rate"]
    corpus = m["corpus"]
    payload = {
        "probe": "probe1-planted-wrong-and-rate",
        "unit_id": "IMP-0318",
        "planted_wrong_fired": planted["fired"],
        "planted_wrong_first": planted["first_outcome"],
        "planted_wrong_final": planted["final_outcome"],
        "planted_wrong_overturned": planted["outcome_changed"],
        "remediations_executed": planted["executed"],
        "counterexample_id": planted["counterexample_id"],
        "triggered_runs": rate["triggered"],
        "changed_runs": rate["changed"],
        "outcome_change_rate": rate["rate"],
        "rate_status": rate["rate_status"],
        "planted_wrong_all_overturned": corpus["planted_wrong_all_overturned"],
        "theatre": corpus["theatre"],
        "pass": bool(
            planted["ok"]
            and planted["outcome_changed"]
            and corpus["planted_wrong_all_overturned"]
            and (not corpus["theatre"])
            and rate["rate_status"] == "measured"
            and rate["triggered"] == 20
            and rate["changed"] == 12
            and rate["rate"] == 0.6
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0318-probe1 planted-wrong not overturned or rate unpublished")
        return 1
    print(
        f"outcome_change_rate={rate['rate']} "
        f"changed={rate['changed']}/{rate['triggered']} "
        f"canonical {planted['first_outcome']} -> {planted['final_outcome']}"
    )
    print("SUCCESS:IMP-0318-probe1 planted-wrong overturned; 20-run rate measured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
