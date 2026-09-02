#!/usr/bin/env python3
"""Probe 2: synthetic optimizer control plus append-only metric retirement.

Optimise a deliberately gameable metric, confirm decay is detected, demote
the metric, then prove history bytes are unchanged and rewrite is refused.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.goodhart import (  # noqa: E402
    correlation_series,
    detect_goodhart,
    evaluate_metric_gain,
)
from bench.ledger import LedgerImmutableError, ResultsLedger  # noqa: E402
from bench.simulate import GAMEABLE_METRIC, OUTCOME_ID, simulate_campaign  # noqa: E402

UNIT = "TST-0308"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="tst0308-p2-"))
    ledger = ResultsLedger(tmp / "runs.jsonl")
    rows = simulate_campaign("goodhart", n_cases=32, n_iters=6, seed=308)
    ledger.append_runs(rows)
    before = ledger.snapshot_bytes()
    history_before = list(ledger.history(GAMEABLE_METRIC))

    series = correlation_series(
        ledger.run_records(GAMEABLE_METRIC),
        metric_id=GAMEABLE_METRIC,
        outcome_id=OUTCOME_ID,
    )
    finding = detect_goodhart(series)
    live = evaluate_metric_gain(series)
    if not finding.fired or finding.severity != "P1":
        return fail(f"optimizer control missed decay: {finding.reason}")
    if live["celebrate"]:
        return fail("platform celebrated the gamed metric gain")

    event = ledger.demote_metric(
        GAMEABLE_METRIC,
        reason="goodhart-decay",
        iteration=int(series[-1]["iteration"]),
        finding={
            "severity": finding.severity,
            "corr_delta": finding.corr_delta,
            "metric_gain": finding.metric_gain,
            "outcome_delta": finding.outcome_delta,
        },
    )
    after = ledger.snapshot_bytes()
    if not after.startswith(before):
        return fail("demotion rewrote historical ledger bytes")
    if len(after) <= len(before):
        return fail("demotion did not append a status event")
    if ledger.history(GAMEABLE_METRIC) != history_before:
        return fail("history() changed after demotion")
    if GAMEABLE_METRIC in ledger.active_metric_ids():
        return fail("demoted metric still active")
    if ledger.scoring_runs(GAMEABLE_METRIC):
        return fail("demoted metric still in current scoring view")
    if not ledger.verify_chain():
        return fail("hash chain broken after demotion")

    rewrite_refused = False
    try:
        ledger.rewrite_run(1, metric_value=0.0)
    except LedgerImmutableError:
        rewrite_refused = True
    if not rewrite_refused:
        return fail("rewrite_run mutated history")
    if ledger.snapshot_bytes() != after:
        return fail("failed rewrite still mutated the file")

    payload = {
        "probe": "probe2-control-and-retire",
        "unit_id": UNIT,
        "synthetic_optimizer": {
            "metric_id": GAMEABLE_METRIC,
            "outcome_id": OUTCOME_ID,
            "n_iterations": len(series),
            "n_runs": len(history_before),
            "series": series,
            "finding": finding.as_dict(),
            "celebrate": live["celebrate"],
            "severity": live["severity"],
        },
        "retirement": {
            "status_event_seq": event["seq"],
            "status": event["status"],
            "reason": event["reason"],
            "history_row_count": len(history_before),
            "history_unchanged": True,
            "prefix_bytes_unchanged": True,
            "active_after": ledger.active_metric_ids(),
            "scoring_view_empty": True,
            "rewrite_refused": True,
            "chain_verified": True,
            "before_bytes": len(before),
            "after_bytes": len(after),
        },
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:TST-0308-probe2 "
        f"P1={finding.fired} demoted={event['status']} "
        f"history_rows={len(history_before)} rewrite_refused={rewrite_refused}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
