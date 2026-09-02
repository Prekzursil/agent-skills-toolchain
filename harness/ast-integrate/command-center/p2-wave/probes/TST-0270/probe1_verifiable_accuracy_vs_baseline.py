#!/usr/bin/env python3
"""Probe 1: per-seat verifiable accuracy vs non-expert baseline.

True expert beats baseline and keeps the weight premium. A labelled expert
at or below baseline (hallucinated, borderline) is refused. Both-states:
honest policy refuses the leak; always-grant mutant still pays the premium.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.antifail.expertise import (  # noqa: E402
    BASE_WEIGHT,
    EXPERT_WEIGHT,
    both_states_weight_refusal,
    per_seat_accuracy_table,
    run_panel,
)


def main() -> int:
    panel = run_panel()
    table = per_seat_accuracy_table(panel)
    both = both_states_weight_refusal(panel)
    by_id = panel["by_id"]
    true = by_id["true-expert"]
    hall = by_id["hallucinated-expert"]
    border = by_id["borderline-expert"]
    base = by_id["non-expert-baseline"]
    ok = bool(
        both["pass"]
        and true["verifiable_accuracy"] > panel["baseline_accuracy"]
        and true["weight"] == EXPERT_WEIGHT
        and hall["verifiable_accuracy"] <= panel["baseline_accuracy"]
        and hall["weight"] == BASE_WEIGHT
        and border["verifiable_accuracy"] == base["verifiable_accuracy"]
        and border["weight_premium_refused"]
        and abs(panel["baseline_accuracy"] - base["verifiable_accuracy"]) < 1e-12
    )
    payload = {
        "probe": "probe1-verifiable-accuracy-vs-baseline",
        "unit_id": "TST-0270",
        "baseline_accuracy": panel["baseline_accuracy"],
        "per_seat": table["rows"],
        "both_states_weight_refusal": both,
        "pass": ok,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not ok:
        print("FAILED:TST-0270-probe1 verifiable accuracy vs baseline")
        return 1
    print(
        "SUCCESS:TST-0270-probe1 true-expert beats baseline and keeps premium; "
        f"hallucinated/borderline refused (baseline={panel['baseline_accuracy']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
