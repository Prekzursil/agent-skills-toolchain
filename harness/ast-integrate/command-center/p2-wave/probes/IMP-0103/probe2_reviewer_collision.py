#!/usr/bin/env python3
"""Named probe 2: reviewer collision pair, false-merge rate, declared threshold.

Mechanically different from probe 1: does not re-run the reverse_engineering
decision. Loads reviewer_pairs.json, computes SequenceMatcher scores, reports
the false-merge rate, asserts the threshold is a params-file value, and runs
the catalog test file (casing, over-length, new, live keywords).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

from tag_gate import (  # noqa: E402
    false_merge_report,
    load_params,
    load_plugin_keywords,
    load_reviewer_pairs,
    similarity,
    validate_category,
    validate_free_tag,
)


def main() -> int:
    params = load_params()
    threshold = float(params["similarity_threshold"])
    src = (REPO / "tools" / "marketplace" / "tag_gate.py").read_text(encoding="utf-8")
    literal = json.dumps(threshold)
    if literal in src:
        print(f"FAILED:IMP-0103-probe2 threshold {literal} is a magic number in tag_gate.py")
        return 1
    if params["similarity_metric"] != "difflib.SequenceMatcher.ratio":
        print("FAILED:IMP-0103-probe2 undeclared similarity metric")
        return 1

    spec = load_reviewer_pairs()
    a, b = spec["reviewer_collision_pair"]
    score = similarity(a, b)
    report = false_merge_report()
    colliding = [p for p in report["pairs"] if {p["a"], p["b"]} == {a, b}]
    if not colliding or not colliding[0]["merged"]:
        print(json.dumps({"score": score, "report": report}, indent=2))
        print("FAILED:IMP-0103-probe2 reviewer pair did not collide")
        return 1
    if report["false_merge_rate"] is None or report["n"] != 8:
        print(json.dumps(report, indent=2))
        print("FAILED:IMP-0103-probe2 false-merge fixture size unexpected")
        return 1

    existing = load_plugin_keywords(REPO)
    casing = validate_free_tag("Reverse-Engineering", existing)
    over = validate_free_tag("a" * (int(params["max_length"]) + 1), existing)
    if not casing.accepted or casing.reason != "already-present":
        print("FAILED:IMP-0103-probe2 casing variant not accepted as already-present")
        return 1
    if over.accepted or over.reason != "over-length":
        print("FAILED:IMP-0103-probe2 over-length tag was not refused")
        return 1

    cat_ok = validate_category("security")
    cat_bad = validate_category("not-a-real-category")
    if not cat_ok.accepted or cat_bad.accepted:
        print("FAILED:IMP-0103-probe2 closed category vocabulary did not discriminate")
        return 1

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", "tools/marketplace/tests/test_tag_gate.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    test_out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode != 0 or "SUCCESS:test_tag_gate" not in test_out:
        print(test_out[-3000:])
        print(f"FAILED:IMP-0103-probe2 test_tag_gate exit={proc.returncode}")
        return 1

    result = {
        "probe": "probe2-reviewer-collision-and-false-merge",
        "unit_id": "IMP-0103",
        "reviewer_pair": [a, b],
        "reviewer_score": round(score, 6),
        "reviewer_collides": True,
        "false_merge_rate": report["false_merge_rate"],
        "false_merge_n": report["n"],
        "false_merge_merges": report["merges"],
        "threshold": threshold,
        "metric": params["similarity_metric"],
        "threshold_is_declared_parameter": True,
        "casing_variant_accepted": True,
        "over_length_rejected": True,
        "closed_category_ok": True,
        "test_tag_gate_exit": proc.returncode,
        "pass": True,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    print(
        f"reviewer={a!r}/{b!r} score={score:.4f} false_merge_rate="
        f"{report['false_merge_rate']:.4f} ({report['merges']}/{report['n']})"
    )
    print(
        "SUCCESS:IMP-0103-probe2 reviewer collision, false-merge rate, "
        "declared threshold"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
