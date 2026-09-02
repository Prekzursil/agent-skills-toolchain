#!/usr/bin/env python3
"""Probe 2: remove-one-receipt + open-escalation both-states controls.

Mechanically different from probe 1 (fixture mutants, not live recompute).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import (  # noqa: E402
    build_green,
    mutate_high_error_rate,
    mutate_open_escalation,
    mutate_remove_one_receipt,
)
from gate import compute  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0128-probe2 {msg}")
    return 1


def snapshot(root: Path) -> dict:
    doc = compute(root)
    return {
        "gate_verdict": doc["gate_verdict"],
        "blocking": list(doc["blocking_condition_ids"]),
        "residual_settling_ok": all(
            str(r.get("settling_experiment") or "").strip() for r in doc["residuals"]
        ),
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cnf0128-p2-") as td:
        base = Path(td)

        green_root = base / "green"
        build_green(green_root)
        green = snapshot(green_root)
        if green["gate_verdict"] != "GREEN":
            return fail(f"green-fixture-not-green {green}")
        if not green["residual_settling_ok"]:
            return fail("green-residual-missing-settling")

        rm_root = base / "remove-one"
        build_green(rm_root)
        removed = mutate_remove_one_receipt(rm_root)
        removed_snap = snapshot(rm_root)
        if removed_snap["gate_verdict"] != "RED":
            return fail(f"remove-one-did-not-go-red {removed_snap}")
        if "C-CENSUS" not in removed_snap["blocking"]:
            return fail(f"remove-one-did-not-fail-census {removed_snap}")

        esc_root = base / "escalation"
        build_green(esc_root)
        mutate_open_escalation(esc_root)
        esc = snapshot(esc_root)
        if esc["gate_verdict"] != "RED":
            return fail(f"open-escalation-did-not-block {esc}")
        if "C-ESCALATION" not in esc["blocking"]:
            return fail(f"open-escalation-wrong-condition {esc}")
        # Error rate on this corpus is 0; escalation must still block.
        esc_live = compute(esc_root)
        rate_cond = next(c for c in esc_live["conditions"] if c["id"] == "C-ERROR-RATE")
        if rate_cond.get("computed_state") != "PASS" or rate_cond.get("error_rate") != 0.0:
            return fail(f"escalation-control-needs-zero-error-rate {rate_cond}")

        rate_root = base / "high-rate"
        build_green(rate_root)
        mutate_high_error_rate(rate_root)
        high = snapshot(rate_root)
        if high["gate_verdict"] != "RED" or "C-ERROR-RATE" not in high["blocking"]:
            return fail(f"high-error-rate-did-not-fail {high}")

        empty_root = base / "empty"
        empty_root.mkdir()
        empty = snapshot(empty_root)
        if empty["gate_verdict"] != "RED":
            return fail("empty-corpus-read-as-pass")

    print(
        json.dumps(
            {
                "probe": "probe2-remove-one-receipt",
                "green": green,
                "removed_receipt": removed,
                "after_remove": removed_snap,
                "open_escalation": esc,
                "high_error_rate": high,
                "empty_corpus": empty,
                "went_red": True,
                "open_escalation_blocks_at_zero_error_rate": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"green=GREEN remove_one=RED({removed}) escalation=RED high_rate=RED empty=RED"
    )
    print("SUCCESS:CNF-0128-probe2 remove-one-receipt and open-escalation controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
