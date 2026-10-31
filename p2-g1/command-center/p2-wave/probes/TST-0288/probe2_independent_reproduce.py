#!/usr/bin/env python3
"""TST-0288 probe 2: independent reproduction.

Re-runs the whole harness in a FRESH interpreter under the same seed and
requires the identical ranking, best method and decision flags - the
ranking must not be a lucky draw of one process. Also asserts per_case.json
and ranking_summary.json were written by probe1 with full method coverage.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))


def main() -> int:
    checks: dict[str, bool] = {}
    first = json.loads(
        (HERE / "probe1-paired-rank.raw.txt").read_text(encoding="utf-8")
    )
    code = (
        "import sys, json; sys.path.insert(0, r'"
        + str(HERE)
        + "'); import harness; r = harness.run(); "
        "print(json.dumps({'ranking': r['ranking_by_mean_brier'], "
        "'best': r['best_method'], "
        "'weighting': r['weighting_beats_majority'], "
        "'random': r['random_weights_beats_majority']}))"
    )
    p = subprocess.run(
        [sys.executable, "-I", "-c", code],
        capture_output=True,
        text=True,
        timeout=900,
    )
    if p.returncode != 0:
        print(p.stderr[-500:])
        return 1
    fresh = json.loads(p.stdout.strip().splitlines()[-1])
    checks["ranking_identical"] = fresh["ranking"] == first["ranking_by_mean_brier"]
    checks["best_identical"] = fresh["best"] == first["best_method"]
    checks["weighting_flag_identical"] = (
        fresh["weighting"] == first["weighting_beats_majority"]
    )
    checks["random_flag_identical"] = (
        fresh["random"] == first["random_weights_beats_majority"]
    )

    pc = json.loads((HERE / "per_case.json").read_text(encoding="utf-8"))
    checks["per_case_full_coverage"] = len(pc["per_case"]) == 20
    checks["per_case_n_200_each"] = all(
        len(v) == 200 for v in pc["per_case"].values()
    )
    rs = json.loads((HERE / "ranking_summary.json").read_text(encoding="utf-8"))
    checks["ranking_summary_written"] = rs["best_method"] == first["best_method"]

    out = {
        "probe": "probe2_independent_reproduce",
        "unit": "TST-0288",
        "fresh_process_ranking_identical": checks["ranking_identical"],
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe2-reproduce.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
