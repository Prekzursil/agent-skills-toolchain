#!/usr/bin/env python3
"""TST-0265 probe 1: planted mutants + both-states control.

For each planted mutant class, the detector must FIRE (the pair collapses)
and the probe records which signal fired. The blind class
(oov_deep_paraphrase) must stay SILENT. Both-states: a fixture of 100
genuinely distinct ideas must collapse by less than the declared tolerance,
proving the detector is not simply aggressive.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from fixtures import BLIND_PAIR, MUTANT_PAIRS, distinct_100  # noqa: E402
from measure import run_count  # noqa: E402

sys.path.insert(0, str(REPO / "tools"))
from council.quota.unique_ideas import _raw_jaccard  # noqa: E402


def main() -> int:
    checks: dict[str, bool] = {}
    mutants: dict[str, dict] = {}
    for cls, (a, b) in sorted(MUTANT_PAIRS.items()):
        info = run_count([a, b])
        fired = info["post_dedup_count"] < 2
        mutants[cls] = {
            "want": "FIRE",
            "observed": "FIRE" if fired else "SILENT",
            "raw_jaccard": round(_raw_jaccard(a, b), 3),
            "post_pair_count": info["post_dedup_count"],
            "passed": fired,
        }
        checks[f"mutant_{cls}_fires"] = fired
    blind = run_count(list(BLIND_PAIR))
    blind_fired = blind["post_dedup_count"] < 2
    mutants["oov_deep_paraphrase"] = {
        "want": "SILENT",
        "observed": "SILENT" if not blind_fired else "FIRE",
        "raw_jaccard": round(_raw_jaccard(*BLIND_PAIR), 3),
        "post_pair_count": blind["post_dedup_count"],
        "passed": not blind_fired,
    }
    checks["blind_class_silent"] = not blind_fired

    distinct = distinct_100()
    d = run_count(distinct)
    checks["distinct_raw_100"] = d["raw_count"] == 100
    checks["distinct_post_100"] = d["post_dedup_count"] == 100
    checks["distinct_collapse_under_tolerance"] = d["collapse_ratio"] < 0.05

    out = {
        "probe": "probe1_mutants_both_states",
        "unit": "TST-0265",
        "similarity_method": "raw-token-jaccard-OR-folded-mechanism-key",
        "jaccard_threshold": 0.5,
        "planted_mutants": mutants,
        "distinct_100": {
            "raw_count": d["raw_count"],
            "post_dedup_count": d["post_dedup_count"],
            "collapse_ratio": d["collapse_ratio"],
            "tolerance": 0.05,
        },
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe1-mutants.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
