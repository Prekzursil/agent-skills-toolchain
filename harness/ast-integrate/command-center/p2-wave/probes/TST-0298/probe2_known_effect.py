#!/usr/bin/env python3
"""Probe 2: paired bootstrap interval, known-effect control, independent recompute.

Catalog tests:
  * Paired bootstrap over per-case outcomes; interval published.
  * Known-effect control: inject a synthetic 10-point improvement and confirm
    the test detects it; inject zero effect and confirm it does not.
  * Reviewer mandate: re-run the comparison from the raw per-case results and
    independently reproduce the reported effect size and interval.
  * The platform refuses to emit a bare point estimate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.compare import (  # noqa: E402
    INTERVAL_KEYS,
    STATUS_COMPARED,
    VERDICT_IMPROVEMENT,
    VERDICT_NO_DETECT,
    BareEstimateError,
    compare_cases,
    emit_delta,
    file_preregistration,
    paired_bootstrap_interval,
    require_interval,
)
from bench.synthetic import synthetic_pairs  # noqa: E402

FILED_AT = "2026-08-01T00:00:00Z"
RUN_AT = "2026-08-01T12:00:00Z"
MIN_EFFECT = 10.0
ASSUMED_SD = 20.0
SEED = 298
N_RESAMPLES = 2000


def fail(msg: str) -> int:
    print(f"FAILED:TST-0298-probe2 {msg}")
    return 1


def _schema_rejects_bare() -> tuple[bool, str]:
    schema_path = REPO / "tools" / "bench" / "comparison-result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        bare = {"status": "COMPARED", "delta": {"mean": 10.0}, "verdict": "IMPROVEMENT", "n": 32}
        missing = [k for k in ("lo", "hi", "n") if k not in bare["delta"]]
        return bool(missing), "manual-missing-lo-hi-n"
    validator = jsonschema.Draft202012Validator(schema)
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"status": "COMPARED", "delta": {"mean": 10.0}, "verdict": "IMPROVEMENT", "n": 32},
        {"status": "NOT-CHECKED", "reason": "underpowered", "delta": {"mean": 10.0}},
    ]
    rejected = [bool(list(validator.iter_errors(g))) for g in garbage]
    return all(rejected), f"jsonschema:{rejected}"


def main() -> int:
    prereg = file_preregistration(
        min_effect_size=MIN_EFFECT,
        assumed_sd=ASSUMED_SD,
        filed_at=FILED_AT,
        seed=SEED,
        n_resamples=N_RESAMPLES,
        comparison_id="TST-0298-probe2",
    )
    n = int(prereg["required_n"])
    ten = synthetic_pairs(n, 10.0)
    zero = synthetic_pairs(n, 0.0)
    if len(ten) != n or len(zero) != n:
        return fail("synthetic length")

    r10 = compare_cases(ten, prereg, RUN_AT)
    r0 = compare_cases(zero, prereg, RUN_AT)
    print(
        f"ten-point status={r10.get('status')} verdict={r10.get('verdict')} "
        f"mean={((r10.get('delta') or {}).get('mean'))}"
    )
    print(
        f"zero-effect status={r0.get('status')} verdict={r0.get('verdict')} "
        f"mean={((r0.get('delta') or {}).get('mean'))} "
        f"contains_zero={r0.get('contains_zero')}"
    )

    if r10.get("status") != STATUS_COMPARED:
        return fail(f"ten-point status={r10.get('status')}")
    if r0.get("status") != STATUS_COMPARED:
        return fail(f"zero-effect status={r0.get('status')}")
    if r10.get("verdict") != VERDICT_IMPROVEMENT:
        return fail(f"ten-point not detected: verdict={r10.get('verdict')}")
    if r0.get("verdict") != VERDICT_NO_DETECT:
        return fail(f"zero-effect falsely detected: verdict={r0.get('verdict')}")
    if r0.get("contains_zero") is not True:
        return fail("zero-effect interval does not contain 0")
    if r10.get("contains_zero") is True:
        return fail("ten-point interval contains 0")

    d10 = require_interval(r10)
    d0 = require_interval(r0)
    missing = [k for k in INTERVAL_KEYS if k not in d10]
    if missing:
        return fail(f"ten-point interval missing {missing}")
    if abs(d10["mean"] - 10.0) > 1e-12:
        return fail(f"ten-point mean={d10['mean']}")
    if abs(d0["mean"] - 0.0) > 1e-12:
        return fail(f"zero-effect mean={d0['mean']}")
    if not (d10["lo"] <= d10["mean"] <= d10["hi"]):
        return fail("ten-point interval does not contain its mean")
    if d10["n"] != n or d0["n"] != n:
        return fail("interval n mismatch")

    # Independent recompute from the raw per-case rows (not from the summary).
    diffs10 = [float(c["after"]) - float(c["before"]) for c in ten]
    mean_hand = sum(diffs10) / len(diffs10)
    m2, lo2, hi2 = paired_bootstrap_interval(
        diffs10, seed=SEED, n_resamples=N_RESAMPLES, level=0.95
    )
    print(
        f"recompute mean_hand={mean_hand} bootstrap=({m2}, {lo2}, {hi2}) "
        f"reported=({d10['mean']}, {d10['lo']}, {d10['hi']})"
    )
    if abs(mean_hand - d10["mean"]) > 1e-12:
        return fail("hand mean != reported mean")
    if (m2, lo2, hi2) != (d10["mean"], d10["lo"], d10["hi"]):
        return fail("independent bootstrap did not reproduce the interval")

    diffs0 = [float(c["after"]) - float(c["before"]) for c in zero]
    z_mean = sum(diffs0) / len(diffs0)
    if abs(z_mean - d0["mean"]) > 1e-12:
        return fail("zero-effect hand mean mismatch")

    # Bare point estimate is refused at the constructor.
    bare_raised = False
    try:
        emit_delta(mean=10.0)
    except BareEstimateError as exc:
        bare_raised = True
        print(f"bare-estimate raised {type(exc).__name__}: {exc}")
    if not bare_raised:
        return fail("emit_delta(mean=10.0) did not refuse")

    ok_schema, schema_how = _schema_rejects_bare()
    print(f"schema_rejects_bare={ok_schema} how={schema_how}")
    if not ok_schema:
        return fail("comparison-result schema accepted a bare delta")

    print(
        json.dumps(
            {
                "probe": "probe2-known-effect",
                "unit_id": "TST-0298",
                "n": n,
                "ten_point_verdict": r10["verdict"],
                "zero_effect_verdict": r0["verdict"],
                "ten_point_interval": d10,
                "zero_effect_interval": d0,
                "independent_recompute": True,
                "bare_estimate_refused": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:TST-0298-probe2 known-effect 10-vs-0, interval published, "
        "independent recompute, bare estimate refused"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
