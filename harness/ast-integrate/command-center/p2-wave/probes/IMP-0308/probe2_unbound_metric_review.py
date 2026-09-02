#!/usr/bin/env python3
"""IMP-0308 probe 2: independent review from the tests, not the author's summary.

Negative control: an expression that names an unproduced metric must FAIL at
bind time. Evaluating it must not return false and sit false forever.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.stopping.expr import (  # noqa: E402
    SPEC_EXPRESSIONS,
    BindError,
    bind,
    census,
    evaluate,
    live_run,
    parse,
    spec_producers,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0308-probe2 {msg}")
    return 1


def main() -> int:
    producers = spec_producers()
    ghost = "ghost_metric_never_produced >= 1 AND unique_ideas >= 0"

    bind_fired = False
    try:
        bind(ghost, producers)
    except BindError as exc:
        bind_fired = True
        print(f"bind BindError unproduced={list(exc.unproduced)}")
        if "ghost_metric_never_produced" not in exc.unproduced:
            return fail("BindError did not name the ghost metric")
    if not bind_fired:
        return fail("bind of unproduced metric succeeded")

    eval_fired = False
    try:
        evaluate(ghost, {"unique_ideas": 500})
    except BindError as exc:
        eval_fired = True
        print(f"evaluate BindError unproduced={list(exc.unproduced)}")
        if "ghost_metric_never_produced" not in exc.unproduced:
            return fail("evaluate BindError missed the ghost metric")
    if not eval_fired:
        return fail("evaluate of unproduced metric returned a boolean instead of failing")

    # Same ghost against an empty snapshot: still fail, never False.
    try:
        val = evaluate("ghost_metric_never_produced == true", {})
        return fail(f"empty-snapshot evaluate returned {val} (must raise)")
    except BindError:
        print("empty-snapshot evaluate raised BindError (not silent false)")

    rows = census([ghost, SPEC_EXPRESSIONS[0][2]], producers)
    unbound = [r for r in rows if r["produced"] is False]
    bound = [r for r in rows if r["produced"] is True]
    print("census_unbound", unbound)
    print("census_bound_sample", bound[:2])
    if not any(r["metric"] == "ghost_metric_never_produced" for r in unbound):
        return fail("census omitted the unproduced metric")
    if not any(r["metric"] == "unique_ideas" and r["produced"] for r in bound):
        return fail("census missed a produced spec metric")

    # Reviewer re-runs the six spec expressions from the tests, not a summary.
    run = live_run()
    for eid, line, src in SPEC_EXPRESSIONS:
        parse(src)
        series = run["series"][eid]
        print(
            f"review {eid} line={line} src={src} series={series} changed={run['changed_during_run'][eid]}"
        )
        if True not in series or False not in series:
            return fail(f"{eid} did not both-states on the live run")

    print("reviewer_verdict PASS independent=True start=tests")
    print("SUCCESS:IMP-0308-probe2 unbound-metric bind-time fail and independent review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
