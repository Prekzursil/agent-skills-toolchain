#!/usr/bin/env python
"""Five-run CI regression gate for the existing semantic-router benchmark.

The weekly ``bench.py`` producer remains fail-open and owns baseline ratcheting plus
background-digest reporting. This adapter is read-only: it runs that producer's evaluator
five times, refuses to judge noisy or malformed results, and exits non-zero only for a
deterministic regression against the committed baseline. CI initially invokes it with
``continue-on-error`` so the new lane burns in as a shadow signal.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

THIS = Path(__file__).resolve().parent
if str(THIS) not in sys.path:
    sys.path.insert(0, str(THIS))

import bench  # noqa: E402

PROBE_RUNS = 5
COUNT_KEYS = (
    "skill_hit",
    "skill_total",
    "mcp_hit",
    "mcp_total",
    "neg_fire",
    "neg_total",
)


def _valid_counts(result: object) -> bool:
    if not isinstance(result, dict):
        return False
    if not all(type(result.get(key)) is int for key in COUNT_KEYS):
        return False
    return (
        0 <= result["skill_hit"] <= result["skill_total"]
        and 0 <= result["mcp_hit"] <= result["mcp_total"]
        and 0 <= result["neg_fire"] <= result["neg_total"]
    )


def _valid_probe(result: object) -> bool:
    if not _valid_counts(result):
        return False
    outcomes = result.get("case_outcomes")
    if not isinstance(outcomes, list) or not outcomes:
        return False
    case_ids: set[int] = set()
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            return False
        case_id = outcome.get("case")
        values = tuple(
            outcome.get(key) for key in ("skill_hit", "mcp_hit", "negative_fire")
        )
        if type(case_id) is not int or case_id in case_ids:
            return False
        if any(value is not None and type(value) is not bool for value in values):
            return False
        case_ids.add(case_id)

    skill_values = [item.get("skill_hit") for item in outcomes]
    mcp_values = [item.get("mcp_hit") for item in outcomes]
    negative_values = [item.get("negative_fire") for item in outcomes]
    return (
        sum(value is not None for value in skill_values) == result["skill_total"]
        and sum(value is True for value in skill_values) == result["skill_hit"]
        and sum(value is not None for value in mcp_values) == result["mcp_total"]
        and sum(value is True for value in mcp_values) == result["mcp_hit"]
        and sum(value is not None for value in negative_values) == result["neg_total"]
        and sum(value is True for value in negative_values) == result["neg_fire"]
    )


def _same_corpus_totals(baseline: dict, current: dict) -> bool:
    return all(
        current[key] == baseline[key]
        for key in ("skill_total", "mcp_total", "neg_total")
    )


def _regression_reasons(baseline: dict, current: dict) -> list[str]:
    reasons = []
    if current["skill_hit"] < baseline["skill_hit"]:
        reasons.append(
            f"skill {baseline['skill_hit']}/{baseline['skill_total']}"
            f"->{current['skill_hit']}/{current['skill_total']}"
        )
    if current["mcp_hit"] < baseline["mcp_hit"]:
        reasons.append(
            f"mcp {baseline['mcp_hit']}/{baseline['mcp_total']}"
            f"->{current['mcp_hit']}/{current['mcp_total']}"
        )
    if current["neg_fire"] > baseline["neg_fire"]:
        reasons.append(
            f"negative-fire {baseline['neg_fire']}/{baseline['neg_total']}"
            f"->{current['neg_fire']}/{current['neg_total']}"
        )
    return reasons


def run_gate(
    *,
    runs: int = PROBE_RUNS,
    eval_runner: Callable[[], str | None] | None = None,
    baseline_loader: Callable[[], dict | None] | None = None,
    backend_down: Callable[[], bool] | None = None,
) -> int:
    """Return 1 only for a five-run deterministic regression; fail open otherwise."""
    if runs != PROBE_RUNS:
        print(f"INDETERMINATE:routing-regression requires-runs={PROBE_RUNS}")
        return 0

    runner = eval_runner or bench._default_eval_runner
    probes = []
    for run_number in range(1, runs + 1):
        current = bench._parse_hybrid(runner())
        if not _valid_probe(current):
            print(f"INDETERMINATE:routing-regression invalid-eval run={run_number}")
            return 0
        probes.append(current)

    signatures = {
        json.dumps(probe, sort_keys=True, separators=(",", ":")) for probe in probes
    }
    if len(signatures) != 1:
        print(f"NO-GATE:routing-regression nondeterministic runs={runs}")
        return 0

    baseline = (baseline_loader or bench._load_baseline)()
    if not _valid_counts(baseline):
        print("INDETERMINATE:routing-regression invalid-baseline")
        return 0

    current = probes[0]
    if not _same_corpus_totals(baseline, current):
        print("INDETERMINATE:routing-regression corpus-totals-changed")
        return 0

    reasons = _regression_reasons(baseline, current)
    if not reasons:
        print(f"PASS:routing-regression deterministic-runs={runs}")
        return 0

    if (backend_down or bench._semantic_backend_down)():
        print("INDETERMINATE:routing-regression semantic-backend-down")
        return 0

    print(f"FAILED:routing-regression deterministic-runs={runs} " + "; ".join(reasons))
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=PROBE_RUNS)
    args = parser.parse_args(argv)
    try:
        return run_gate(runs=args.runs)
    except Exception as exc:
        print(f"INDETERMINATE:routing-regression {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
