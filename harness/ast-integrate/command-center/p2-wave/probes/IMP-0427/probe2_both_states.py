#!/usr/bin/env python3
"""Probe 2: both-states control — burst 429 storm vs scheduled zero 429s.

Mechanically different from probe 1 (bucket invariants). This re-runs two
arms at identical unit count and refuses a vacuous both-zero result.
Independent reviewer signal: the burst arm must produce 429s, otherwise the
comparison is not a control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from arrival_scheduler import (  # noqa: E402
    both_states_to_dict,
    run_529_concurrency_control,
    run_both_states,
)

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0427.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    cmp = run_both_states()
    rec529 = run_529_concurrency_control()
    same_n = cmp.burst.n_units == cmp.scheduled.n_units
    burst_control = cmp.burst.n_429 > 0
    scheduled_clean = cmp.scheduled.n_429 == 0
    not_vacuous = not cmp.vacuous
    receipt_match = None
    if RECEIPT.is_file() and RECEIPT.stat().st_size > 0:
        doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
        published = doc.get("both_states") or {}
        burst_n = (published.get("burst") or {}).get("n_429")
        sched_n = (published.get("scheduled") or {}).get("n_429")
        units_n = published.get("n_units")
        receipt_match = (
            burst_n == cmp.burst.n_429
            and sched_n == cmp.scheduled.n_429
            and units_n == cmp.n_units
            and str(doc.get("state") or "").upper() not in NOT_DELIVERING
        )

    payload = {
        "probe": "probe2-both-states",
        "unit_id": "IMP-0427",
        "both_states": both_states_to_dict(cmp),
        "same_unit_count": same_n,
        "burst_429": cmp.burst.n_429,
        "scheduled_429": cmp.scheduled.n_429,
        "burst_is_real_control": burst_control,
        "scheduler_avoids_storm": scheduled_clean,
        "vacuous": cmp.vacuous,
        "load_escalations": cmp.load_escalations,
        "provider_529": rec529,
        "receipt_present": RECEIPT.is_file(),
        "receipt_match": receipt_match,
        "pass": (
            same_n
            and burst_control
            and scheduled_clean
            and not_vacuous
            and rec529["concurrency_unchanged"]
            and rec529["all_succeeded"]
            and rec529["n_529_observed"] > 0
            and (receipt_match is not False)
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not same_n:
        print("FAILED:IMP-0427-probe2 unit counts differ across arms")
        return 1
    if not burst_control or cmp.vacuous:
        print("FAILED:IMP-0427-probe2 vacuous control (burst produced no 429s)")
        return 1
    if not scheduled_clean:
        print(f"FAILED:IMP-0427-probe2 scheduler 429s={cmp.scheduled.n_429}")
        return 1
    if not rec529["concurrency_unchanged"] or not rec529["all_succeeded"]:
        print("FAILED:IMP-0427-probe2 529 mutated concurrency or lost work")
        return 1
    if receipt_match is False:
        print("FAILED:IMP-0427-probe2 receipt 429 counts do not match live rerun")
        return 1
    print(
        f"n={cmp.n_units} burst_429={cmp.burst.n_429} scheduled_429={cmp.scheduled.n_429} "
        f"529_cap_unchanged={rec529['concurrency_unchanged']}"
    )
    print("SUCCESS:IMP-0427-probe2 burst storm vs scheduled zero-429 (real control)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
