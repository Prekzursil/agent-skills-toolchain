#!/usr/bin/env python3
"""Probe 2: repository size at which the graph approach becomes too slow."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402
import ranking  # noqa: E402


def main() -> int:
    doc = C.load_doc()
    scale_errs = C.scale_errors(doc)
    mutant = C.mutant_missing_scale(doc)
    mutant_errs = C.scale_errors(mutant)
    live = ranking.scale_report()
    recorded = int((doc.get("scale_limit") or {}).get("n_files") or 0)
    live_n = int(live["too_slow_repository_size"]["n_files"])
    ratio = (live_n / recorded) if recorded else 0.0
    within = recorded > 0 and 0.5 <= ratio <= 2.0
    pr_20k = next(
        (r for r in live["pagerank"]["rows"] if r["n_files"] == 20000),
        None,
    )
    pagerank_not_limiter = bool(pr_20k and pr_20k["seconds"] < 2.0)

    payload = {
        "probe": "probe2-scale-limit",
        "unit_id": "RES-0107",
        "reviewer_id": "RES-0107-probe2-scale-and-refuter",
        "recorded_n_files": recorded,
        "live_n_files": live_n,
        "ratio_live_over_recorded": round(ratio, 3),
        "within_2x": within,
        "pagerank_20k": pr_20k,
        "pagerank_not_limiter": pagerank_not_limiter,
        "good_scale": {"pass": not scale_errs, "errors": scale_errs},
        "mutant_missing_n_files": {
            "id": "NC-scale-limit-missing-n-files",
            "must_fail": True,
            "failed": bool(mutant_errs),
            "errors": mutant_errs,
        },
        "tree_sitter_invoked": False,
        "pass": False,
    }
    payload["pass"] = bool(
        payload["good_scale"]["pass"]
        and payload["mutant_missing_n_files"]["failed"]
        and within
        and pagerank_not_limiter
        and recorded >= 1000
    )
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if not payload["pass"]:
        print("FAILED:RES-0107-probe2 scale limit")
        return 1
    print(
        "SUCCESS:RES-0107-probe2 scale limit "
        f"n_files={recorded} live={live_n}; missing-size mutant fails; "
        "PageRank not limiter at 20k"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
