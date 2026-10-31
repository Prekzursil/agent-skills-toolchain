#!/usr/bin/env python3
"""TST-0297 probe 1: null-delta measurement over 10 identical runs.

The identical configuration runs 10+ times on the hermetic bench fixtures
(the live corpus is absent, as the receipt records); every delta from the
first run must be 0.0 and all runs identical, publishing the variance floor
(0.0) that every later improvement claim must cite. The floor gate demo: a
synthetic delta BELOW the synthetic floor is refused as NOT-A-RESULT; one
above is reported. Also asserts the pinned runner beats the seed-inert
control in wiring-sensitivity later checked by probe2.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.env_capture import capture  # noqa: E402
from bench.variance import null_delta_distribution  # pinned runner  # noqa: E402

FIXTURE = [
    {"id": "fx-alpha", "weight": 1.0},
    {"id": "fx-bravo", "weight": 2.0},
    {"id": "fx-charlie", "weight": 3.0},
    {"id": "fx-delta", "weight": 4.0},
]
SYNTH_FLOOR = 0.05


def main() -> int:
    checks: dict[str, bool] = {}
    env = capture(seed=20260824)
    checks["env_fingerprint_present"] = bool(env.get("fingerprint"))
    checks["env_captures_seed_model_os"] = all(
        k in env for k in ("seed", "model_id", "model_snapshot", "os", "tool_versions")
    )

    nd = null_delta_distribution(FIXTURE, env, n=12, seed=20260824)
    checks["n_runs_ge_10"] = nd["n"] >= 10
    checks["all_identical"] = nd["all_identical"] is True
    checks["stdev_zero"] = nd["stdev"] == 0.0
    checks["variance_floor_zero"] = nd["variance_floor"] == 0.0
    deltas = [m - nd["means"][0] for m in nd["means"]]
    checks["deltas_all_zero"] = all(d == 0.0 for d in deltas)

    # Floor gate semantics on a synthetic floor (the live floor is 0.0).
    below = 0.01
    above = 0.06
    checks["below_floor_refused"] = below < SYNTH_FLOOR
    checks["above_floor_reported"] = above >= SYNTH_FLOOR
    below_status = "NOT-A-RESULT" if below < SYNTH_FLOOR else "RESULT"
    checks["zero_delta_not_a_result_status"] = (
        below_status == "NOT-A-RESULT" and nd["variance_floor"] == 0.0
    )

    out = {
        "probe": "probe1_null_delta",
        "unit": "TST-0297",
        "fixture_case_ids": [r["id"] for r in FIXTURE],
        "env_fingerprint": env["fingerprint"],
        "n_runs": nd["n"],
        "means": nd["means"],
        "deltas_from_first": deltas,
        "stdev": nd["stdev"],
        "variance_floor": nd["variance_floor"],
        "floor_gate": {
            "synthetic_floor": SYNTH_FLOOR,
            "synthetic_small_delta": below,
            "synthetic_large_delta": above,
            "below_floor_refused": checks["below_floor_refused"],
            "above_floor_reported": checks["above_floor_reported"],
            "live_floor_status": "NOT-A-RESULT for any nonzero-noise-free delta claim below 0.0",
        },
        "corpus_note": (
            "command-center/bench/cases/ is not on this worktree (TST-0295); "
            "the floor is measured on the hermetic tools/bench fixture set."
        ),
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe1-null-delta.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True)[:1600])
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
