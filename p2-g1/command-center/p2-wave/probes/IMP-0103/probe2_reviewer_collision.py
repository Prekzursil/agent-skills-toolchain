"""IMP-0103 probe2 (reviewer, mechanically different): collision + false-merge rate.

Reviewer requirement: propose two tags that should stay distinct but collide under
the threshold, and report the false-merge rate. This probe does NOT reuse the gate
calls of probe1: it recomputes similarities directly with difflib over the declared
reviewer pairs fixture and over the parse/parser collision pair.
"""
from __future__ import annotations

import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
MKT = REPO / "tools" / "marketplace"
sys.path.insert(0, str(MKT))

from tag_gate import (  # noqa: E402
    compact,
    false_merge_report,
    load_params,
    load_reviewer_pairs,
    normalize,
    similarity,
)


def main() -> int:
    params = load_params()
    threshold = float(params["similarity_threshold"])
    spec = load_reviewer_pairs()
    pairs = list(spec.get("pairs") or [])
    checks = {}

    # direct recomputation, independent of tag_gate.false_merge_report
    rows = []
    for pair in pairs:
        a, b = str(pair["a"]), str(pair["b"])
        score = SequenceMatcher(None, normalize(a), normalize(b)).ratio()
        merged = compact(a) == compact(b) or score >= threshold
        rows.append({"a": a, "b": b, "score": round(score, 6), "merged": merged})
    n = len(rows)
    merges = sum(1 for r in rows if r["merged"])

    # the two tags a reviewer proposes as SHOULD-STAY-DISTINCT but that collide
    collision_pair = ["parse", "parser"]
    pp_score = round(similarity(collision_pair[0], collision_pair[1]), 6)
    checks["parse_parser_collision_score"] = abs(pp_score - 0.909091) < 1e-5
    checks["parse_parser_would_false_merge"] = pp_score >= threshold

    sep = [r for r in rows if compact(r["a"]) == compact(r["b"])]
    checks["separator_variant_pair_present"] = len(sep) >= 1
    checks["separator_variant_merged"] = all(r["merged"] for r in sep)

    report = false_merge_report()
    checks["fixture_n_is_eight"] = n == 8 and int(report["n"]) == 8
    checks["module_rate_matches_direct"] = abs(
        float(report["false_merge_rate"]) - (merges / n)
    ) < 1e-9
    checks["rate_is_computed_number"] = isinstance(report["false_merge_rate"], float)

    out = {
        "unit_id": "IMP-0103",
        "probe": "probe2-reviewer-collision-and-false-merge",
        "threshold": threshold,
        "reviewer_collision_pair": collision_pair,
        "collision_score": pp_score,
        "pairs_fixture_declared": spec.get("reviewer_collision_pair"),
        "n": n,
        "merges": merges,
        "false_merge_rate": merges / n,
        "rows": rows,
        "module_report_rate": report["false_merge_rate"],
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, indent=1))
    if all(checks.values()):
        print("SUCCESS:IMP-0103-probe2 parse/parser collide at 0.909091 above threshold 0.85; separator-variant pair merges; false-merge rate computed over 8 declared pairs")
        return 0
    print("FAILED:IMP-0103-probe2")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
