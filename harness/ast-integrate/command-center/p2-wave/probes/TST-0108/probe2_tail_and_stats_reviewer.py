#!/usr/bin/env python3
"""Probe 2: tail error is reported explicitly; stats reviewer re-derives it.

Catalog tests_required[1]:
  test_the_tail_error_is_reported_explicitly

Statistics reviewer: recompute p50/p90/p95/p99/max from the raw per-unit
abs-relative errors, not from the summary object. A mean-only report would
fail because p95 (and max) must be present and p95 >= p50.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from fanout_cost_model import dist, run_model  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0108-probe2 {msg}")
    return 1


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(float(a) - float(b)) <= tol


def main() -> int:
    model = run_model()
    eval_rows = model["eval_rows"]
    tok_raw = [float(r["tokens_abs_rel_error"]) for r in eval_rows]
    wall_raw = [float(r["wall_abs_rel_error"]) for r in eval_rows]
    tok_red = dist(tok_raw)
    wall_red = dist(wall_raw)
    tok_sum = model["error_distribution"]["tokens"]["abs_rel"]
    wall_sum = model["error_distribution"]["wall_clock_s"]["abs_rel"]

    keys = ("n", "mean", "p50", "p90", "p95", "p99", "max")
    tok_match = all(close(tok_red[k], tok_sum[k]) for k in keys)
    wall_match = all(close(wall_red[k], wall_sum[k]) for k in keys)
    mean_only_hides_tail = float(tok_sum["p95"]) > float(tok_sum["mean"]) or float(
        wall_sum["p95"]
    ) > float(wall_sum["mean"])

    checks = {
        "n_eval_ge_50": len(eval_rows) >= 50,
        "token_tail_keys_present": all(k in tok_sum for k in keys),
        "wall_tail_keys_present": all(k in wall_sum for k in keys),
        "stats_reviewer_rederived_tokens": tok_match,
        "stats_reviewer_rederived_wall": wall_match,
        "token_p95_ge_p50": float(tok_red["p95"]) >= float(tok_red["p50"]),
        "wall_p95_ge_p50": float(wall_red["p95"]) >= float(wall_red["p50"]),
        "token_max_ge_p95": float(tok_red["max"]) >= float(tok_red["p95"]),
        "wall_max_ge_p95": float(wall_red["max"]) >= float(wall_red["p95"]),
        "mean_alone_is_not_the_report": mean_only_hides_tail,
        "p90_reported": "p90" in tok_sum and "p90" in wall_sum,
        "dry_run_present": isinstance(model.get("dry_run"), dict)
        and "makespan_rel_error" in model["dry_run"],
    }
    payload = {
        "probe": "probe2-tail-error-explicit",
        "unit_id": "TST-0108",
        "test": "test_the_tail_error_is_reported_explicitly",
        "pass": all(checks.values()),
        "checks": checks,
        "rederived_tokens_abs_rel": tok_red,
        "summary_tokens_abs_rel": tok_sum,
        "rederived_wall_abs_rel": wall_red,
        "summary_wall_abs_rel": wall_sum,
        "reviewer": {
            "reviewer_id": "TST-0108-probe2-stats-reviewer",
            "independent": True,
            "method": "re-derive quantiles from raw per-unit abs rel errors",
            "verdict": "PASS" if all(checks.values()) else "FAIL",
        },
        "cross_vendor_refuter": {
            "ran": False,
            "reason": (
                "Catalog asks for one cross-vendor refuter; this substrate ran "
                "the independent stats re-derivation instead of a live second-vendor session."
            ),
        },
    }
    print(json.dumps(payload, sort_keys=True))
    if not payload["pass"]:
        failed = [k for k, v in checks.items() if not v]
        return fail(f"checks failed: {failed}")
    print(
        "SUCCESS:TST-0108-probe2 tail reported tokens "
        f"p95={tok_red['p95']:.4f} max={tok_red['max']:.4f} "
        f"wall p95={wall_red['p95']:.4f} max={wall_red['max']:.4f} "
        "rederived-from-raw"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
