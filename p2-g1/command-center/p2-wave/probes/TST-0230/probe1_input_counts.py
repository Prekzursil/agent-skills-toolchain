#!/usr/bin/env python3
"""TST-0230 probe 1: per-case input counts, floors, and the empty-FLAGGED control.

Live on the production surface platform/lib/foundry/bench.py:
  * every DEFAULT_CASES member emits input_bytes/input_items plus declared
    floors, all above floor, all SCORED (recorded metrics: min 78 bytes / 5
    items across the six default cases);
  * detector control: an intentionally-empty case is FLAGGED, never scored;
  * two-empty regression seed: both planted empty cases are FLAGGED;
  * unguarded-mutant control: an oracle that scores FLAGGED rows goes red.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "platform" / "lib"))

from foundry.bench import (  # noqa: E402
    DEFAULT_CASES,
    Case,
    case_input_metrics,
    case_input_rows,
    input_guard_ok,
)


def main() -> int:
    rows = case_input_rows(DEFAULT_CASES)
    all_emitted = all(
        {"input_bytes", "input_items", "declared_byte_floor", "declared_item_floor"} <= set(r)
        for r in rows
    )
    empty_case = Case(
        id="intentional-empty-control",
        title="detector control: measures nothing",
        required_capabilities=(),
        hazards=(),
        input_bytes=0,
        input_items=0,
    )
    empty_case_2 = Case(
        id="intentional-empty-control-2",
        title="regression seed: second measured-empty benchmark",
        required_capabilities=(),
        hazards=(),
        input_bytes=0,
        input_items=0,
    )
    empty_rows = case_input_rows([empty_case, empty_case_2])
    both_flagged = all(r["outcome"] == "FLAGGED" for r in empty_rows)
    guard_refuses_empties = input_guard_ok([*DEFAULT_CASES, empty_case, empty_case_2]) is False
    guard_accepts_defaults = input_guard_ok(DEFAULT_CASES) is True

    def scoring_oracle(allow_empty: bool) -> bool:
        scored = [r for r in [*rows, *empty_rows] if allow_empty or r["outcome"] == "SCORED"]
        return bool(scored) and all(r["above_declared_floor"] for r in scored)

    mutant_red = scoring_oracle(allow_empty=True) is False
    prod_green = scoring_oracle(allow_empty=False) is True

    assertions = [
        {
            "case_id": r["case_id"],
            "input_bytes": r["input_bytes"],
            "input_items": r["input_items"],
            "declared_byte_floor": r["declared_byte_floor"],
            "declared_item_floor": r["declared_item_floor"],
            "above_declared_floor": r["above_declared_floor"],
            "production_outcome": r["outcome"],
        }
        for r in rows
    ]

    checks = {
        "default_cases_emit_counts_and_floors": all_emitted,
        "all_default_cases_above_floor_scored": all(r["outcome"] == "SCORED" for r in rows),
        "min_bytes_matches_recorded_78": min(r["input_bytes"] for r in rows) == 78,
        "min_items_matches_recorded_5": min(r["input_items"] for r in rows) == 5,
        "detector_control_empty_flagged_not_scored": both_flagged,
        "two_empty_regression_seeds_flagged": len(empty_rows) == 2 and both_flagged,
        "guard_refuses_empty_members": guard_refuses_empties,
        "guard_accepts_production_cases": guard_accepts_defaults,
        "unguarded_mutant_oracle_red": mutant_red,
        "production_oracle_green": prod_green,
    }
    out = {
        "probe": "probe1_input_counts",
        "unit": "TST-0230",
        "case_input_assertions": assertions,
        "empty_control_rows": empty_rows,
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe_input_counts.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
