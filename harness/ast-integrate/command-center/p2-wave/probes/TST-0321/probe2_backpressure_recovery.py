#!/usr/bin/env python3
"""Probe 2: named backpressure, local-stability guard, recovery after storm.

Both-states: live scheduler sheds with a named reason and accounts every
unit; the silent-drop mutant loses units. 10x wall-clock is refused.
After the storm, 1x completed rate returns to the baseline.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scheduler import (  # noqa: E402
    backpressure_both_states,
    local_stability_control,
    recovery_after_storm,
)

ART = REPO / "command-center" / "receipts" / "TST-0321.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0321-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"receipt unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("receipt not an object")
    if doc.get("unit_id") != "TST-0321":
        return fail(f"unit_id {doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    if "SUCCESS:TST-0321" not in text:
        return fail("sentinel absent")

    bp = backpressure_both_states()
    ls = local_stability_control()
    rec = recovery_after_storm()
    print(
        json.dumps(
            {
                "backpressure": {
                    "live_unaccounted": bp["live_unaccounted"],
                    "mutant_unaccounted": bp["mutant_unaccounted"],
                    "live_shed": bp["live_shed"],
                    "mutant_shed": bp["mutant_shed"],
                    "discriminator": bp["discriminator"],
                },
                "local_stability": {
                    "pass": ls["pass"],
                    "wall_10x_refused": ls["wall_10x_refused"],
                    "clock": ls["simulated_10x"].get("clock"),
                    "actually_used": ls["simulated_10x"].get("actually_used"),
                },
                "recovery": {
                    "recovered": rec["recovered"],
                    "baseline_completed_rate": rec["baseline_completed_rate"],
                    "tail_completed_rate": rec["tail_completed_rate"],
                    "storm_n_429": rec["storm_n_429"],
                },
            },
            sort_keys=True,
        )
    )

    if not bp["discriminator"]:
        return fail(
            "silent-drop mutant did not discriminate "
            f"live_unaccounted={bp['live_unaccounted']} "
            f"mutant_unaccounted={bp['mutant_unaccounted']} "
            f"live_shed={bp['live_shed']}"
        )
    if int(bp["live"]["n_unaccounted"]) != 0:
        return fail("live scheduler silently dropped units")
    if not bp["live"]["invariant_ok"]:
        return fail("live backpressure invariant broken")
    if not ls["pass"] or not ls["wall_10x_refused"]:
        return fail("local-stability guard did not refuse 10x wall-clock")
    if ls["simulated_10x"].get("full_rate_wallclock_executed"):
        return fail("10x wall-clock executed on this substrate")
    if not rec["recovered"]:
        return fail(
            "scheduler did not recover after storm "
            f"baseline={rec['baseline_completed_rate']} "
            f"tail={rec['tail_completed_rate']}"
        )
    if int(rec["storm_n_429"]) <= 0:
        return fail("recovery fixture never produced a 429 storm")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in (
        "backpressure-never-silent-drop",
        "local-stability-guard",
        "recovery-after-storm",
    ):
        row = tests.get(tid)
        if not row or row.get("result") != "PASS":
            return fail(f"receipt test {tid} not PASS")

    substrate = (doc.get("substrate") or {}).get("actually_used")
    if substrate != ls["simulated_10x"].get("actually_used"):
        return fail(f"receipt substrate drift {substrate}")

    print(
        f"shed={bp['live_shed']} mutant_unaccounted={bp['mutant_unaccounted']} "
        f"wall_refused={ls['wall_10x_refused']} recovered={rec['recovered']}"
    )
    print("SUCCESS:TST-0321-probe2 backpressure, local-stability, recovery")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
