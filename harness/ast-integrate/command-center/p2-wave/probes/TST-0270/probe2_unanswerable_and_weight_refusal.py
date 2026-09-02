#!/usr/bin/env python3
"""Probe 2: unanswerable control + weight-premium refusal.

An explicit I-do-not-know is silent. A confident answer is a finding even
when verifiable accuracy is high, and honest policy refuses the premium.
Both-states: ignore-unanswerable mutant hides the finding and leaks weight.
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
    both_states_unanswerable,
    both_states_weight_refusal,
    run_panel,
)


def main() -> int:
    panel = run_panel()
    unans = both_states_unanswerable(panel)
    weight = both_states_weight_refusal(panel)
    over = panel["by_id"]["overconfident-expert"]
    true = panel["by_id"]["true-expert"]
    ok = bool(
        unans["pass"]
        and weight["pass"]
        and true["unanswerable_explicit_idk"]
        and not true["unanswerable_confident"]
        and over["unanswerable_confident"]
        and over["findings"]
        and over["verifiable_accuracy"] > over["baseline_accuracy"]
        and over["weight"] == BASE_WEIGHT
        and over["weight_premium_refused"]
    )
    payload = {
        "probe": "probe2-unanswerable-and-weight-refusal",
        "unit_id": "TST-0270",
        "both_states_unanswerable": unans,
        "both_states_weight_refusal": weight,
        "overconfident": {
            "accuracy": over["verifiable_accuracy"],
            "given": over["unanswerable_given"],
            "findings": over["findings"],
            "weight": over["weight"],
            "weight_premium_refused": over["weight_premium_refused"],
        },
        "true_expert_idk": true["unanswerable_given"],
        "pass": ok,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not ok:
        print("FAILED:TST-0270-probe2 unanswerable control or weight refusal")
        return 1
    print(
        "SUCCESS:TST-0270-probe2 explicit IDK silent; confident unanswerable "
        "reported despite high accuracy; weight premium refused"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
