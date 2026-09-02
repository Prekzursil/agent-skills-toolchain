#!/usr/bin/env python3
"""Probe 1: pre-registration order, formula n, and the underpowered guard.

Catalog tests:
  * Pre-registration enforced: a comparison whose pre-registration postdates
    the run is rejected.
  * Underpowered guard: when n is below the pre-registered size, the platform
    emits NOT-CHECKED rather than a delta.

Both-states: the skip_* seams on the same fixtures must emit a delta / accept
the late record, proving the guards (not the fixtures) are what reject.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.compare import (  # noqa: E402
    STATUS_COMPARED,
    STATUS_NOT_CHECKED,
    STATUS_REJECTED,
    compare_cases,
    compute_required_n,
    file_preregistration,
    load_prereg,
    require_interval,
)
from bench.synthetic import synthetic_pairs  # noqa: E402

FILED_AT = "2026-08-01T00:00:00Z"
RUN_AT = "2026-08-01T12:00:00Z"
LATE_AT = "2026-08-02T00:00:00Z"
MIN_EFFECT = 10.0
ASSUMED_SD = 20.0


def fail(msg: str) -> int:
    print(f"FAILED:TST-0298-probe1 {msg}")
    return 1


def has_delta(result: dict) -> bool:
    return "delta" in result and result["delta"] is not None


def main() -> int:
    # 1. n is computed with no outcomes in scope.
    formula_n = compute_required_n(MIN_EFFECT, ASSUMED_SD, 0.05, 0.80)
    if formula_n != 32:
        return fail(f"formula_n={formula_n} want 32")

    prereg = file_preregistration(
        min_effect_size=MIN_EFFECT,
        assumed_sd=ASSUMED_SD,
        filed_at=FILED_AT,
        seed=298,
        n_resamples=2000,
        comparison_id="TST-0298-probe1",
    )
    loaded = load_prereg(prereg)
    if loaded["required_n"] != formula_n or loaded["_formula_n"] != formula_n:
        return fail("required_n was not the pre-computed formula n")
    print(
        f"prereg n={prereg['required_n']} formula={formula_n} "
        f"filed_at={prereg['filed_at']} digest={prereg['digest'][:16]}"
    )

    # Outcomes exist only AFTER n is filed.
    powered = synthetic_pairs(formula_n, 10.0)
    ok = compare_cases(powered, prereg, RUN_AT)
    print(f"timely-powered status={ok.get('status')} verdict={ok.get('verdict')}")
    if ok.get("status") != STATUS_COMPARED:
        return fail(f"timely powered status={ok.get('status')}")
    if has_delta(ok) is False:
        return fail("timely powered missing delta")
    interval = require_interval(ok)
    if interval["n"] != formula_n:
        return fail(f"interval n={interval['n']}")
    for key in ("mean", "lo", "hi", "n"):
        if key not in interval:
            return fail(f"interval missing {key}")

    # 2. Late pre-registration is rejected and carries no delta.
    late = dict(prereg)
    late["filed_at"] = LATE_AT
    late.pop("digest", None)
    late_r = compare_cases(powered, late, RUN_AT)
    print(f"late-prereg status={late_r.get('status')} reason={late_r.get('reason')}")
    if late_r.get("status") != STATUS_REJECTED:
        return fail(f"late prereg status={late_r.get('status')}")
    if late_r.get("reason") != "preregistration-postdates-run":
        return fail(f"late reason={late_r.get('reason')}")
    if has_delta(late_r):
        return fail("late prereg emitted a delta")

    # Both-states: skipping the order check on the SAME late record accepts it.
    late_skip = compare_cases(
        powered, late, RUN_AT, _probe_skip_prereg_order=True
    )
    print(
        f"late-skip-order status={late_skip.get('status')} "
        f"has_delta={has_delta(late_skip)}"
    )
    if late_skip.get("status") != STATUS_COMPARED or not has_delta(late_skip):
        return fail("skip_prereg_order did not accept the late record (guard not load-bearing)")

    # 3. Underpowered: n=4 < 32, NOT-CHECKED, no delta.
    under = json.loads(
        (HERE / "fixtures" / "underpowered.json").read_text(encoding="utf-8")
    )["cases"]
    if len(under) >= formula_n:
        return fail("underpowered fixture is not below required_n")
    weak = compare_cases(under, prereg, RUN_AT)
    print(
        f"underpowered status={weak.get('status')} reason={weak.get('reason')} "
        f"n={weak.get('n')} required_n={weak.get('required_n')}"
    )
    if weak.get("status") != STATUS_NOT_CHECKED:
        return fail(f"underpowered status={weak.get('status')}")
    if weak.get("reason") != "underpowered":
        return fail(f"underpowered reason={weak.get('reason')}")
    if has_delta(weak):
        return fail("underpowered emitted a delta")
    try:
        require_interval(weak)
    except Exception as exc:
        print(f"underpowered require_interval raised {type(exc).__name__}")
    else:
        return fail("require_interval accepted a NOT-CHECKED result")

    # Both-states: skipping the power guard emits a delta on the same 4 rows.
    weak_skip = compare_cases(
        under, prereg, RUN_AT, _probe_skip_power_guard=True
    )
    print(
        f"underpowered-skip-guard status={weak_skip.get('status')} "
        f"has_delta={has_delta(weak_skip)}"
    )
    if weak_skip.get("status") != STATUS_COMPARED or not has_delta(weak_skip):
        return fail("skip_power_guard did not emit a delta (guard not load-bearing)")

    # 4. Tampered required_n (filed 8, formula 32) is rejected.
    tampered = dict(prereg)
    tampered["required_n"] = 8
    tampered.pop("digest", None)
    tamp = compare_cases(powered, tampered, RUN_AT)
    print(f"tampered-n status={tamp.get('status')} reason={tamp.get('reason')}")
    if tamp.get("status") != STATUS_REJECTED:
        return fail(f"tampered n status={tamp.get('status')}")
    if tamp.get("reason") != "sample-size-not-precomputed":
        return fail(f"tampered reason={tamp.get('reason')}")
    if has_delta(tamp):
        return fail("tampered n emitted a delta")

    print(
        json.dumps(
            {
                "probe": "probe1-prereg-and-underpowered",
                "unit_id": "TST-0298",
                "formula_n": formula_n,
                "timely_status": ok["status"],
                "late_status": late_r["status"],
                "late_skip_status": late_skip["status"],
                "underpowered_status": weak["status"],
                "underpowered_skip_status": weak_skip["status"],
                "tampered_status": tamp["status"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:TST-0298-probe1 pre-registration order and underpowered "
        "guard both-states"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
