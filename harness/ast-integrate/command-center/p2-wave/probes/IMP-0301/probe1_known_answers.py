#!/usr/bin/env python3
"""Probe 1: each non-count target type against a fixture with a known answer.

Independent recounts (Counter / set Jaccard / Simpson) are compared to
evaluate() rather than trusting the author's receipt summary.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    declared,
    evaluate,
    independent_counts,
    independent_jaccard,
    independent_simpson,
    independent_tokens,
    load,
    result_by_id,
    spec,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0301-probe1 {msg}")
    return 1


def main() -> int:
    council = spec()
    kinds_present = {
        str(t.get("kind"))
        for t in council["targets"]
        if str(t.get("kind")) != "unique_idea"
    }
    required = {
        "novelty",
        "diversity",
        "category",
        "coverage",
        "objection",
        "evidence",
        "counterexample",
    }
    if kinds_present != required:
        return fail(f"kinds {sorted(kinds_present)} != {sorted(required)}")

    empty = load("snapshot_empty_gamma.json")
    full = load("snapshot_full.json")
    clustered = load("snapshot_clustered.json")
    spread = load("snapshot_spread.json")
    miss = load("snapshot_floors_miss.json")

    r_empty = evaluate(council, empty)
    r_full = evaluate(council, full)
    r_cl = evaluate(council, clustered)
    r_sp = evaluate(council, spread)
    r_miss = evaluate(council, miss)

    if r_empty.get("skipped_count_targets") != ["t-unique"]:
        return fail(f"count skip {r_empty.get('skipped_count_targets')}")

    cats = declared()
    ind_empty = independent_counts(empty["ideas"], cats)
    cov = result_by_id(r_empty, "t-coverage")
    table = {row["category"]: row["count"] for row in cov["per_category"]}
    if table != ind_empty:
        return fail(f"coverage table {table} != independent {ind_empty}")
    if ind_empty["gamma"] != 0:
        return fail("fixture gamma was not empty")
    if cov.get("pass") is not False:
        return fail("empty gamma must FAIL per-category coverage")
    if "gamma" not in cov.get("empty_categories", []):
        return fail("gamma missing from empty_categories")
    if cov.get("aggregate_would_pass") is not True:
        return fail("aggregate 2/3 must pass 0.5 threshold (disagreement fixture)")
    if cov.get("aggregate_and_per_category_disagree") is not True:
        return fail("aggregate vs per-category must disagree on empty-gamma")

    cov_full = result_by_id(r_full, "t-coverage")
    ind_full = independent_counts(full["ideas"], cats)
    if any(v < 1 for v in ind_full.values()):
        return fail(f"full fixture not fully occupied {ind_full}")
    if cov_full.get("pass") is not True:
        return fail("full snapshot coverage must PASS")
    if cov_full.get("empty_categories"):
        return fail(f"full empties {cov_full.get('empty_categories')}")

    cat_empty = result_by_id(r_empty, "t-category")
    cat_full = result_by_id(r_full, "t-category")
    if cat_empty.get("pass") is not False:
        return fail("category min=2 must FAIL on empty gamma")
    if cat_full.get("pass") is not True:
        return fail("category min=2 must PASS on 2/2/2")

    nov = result_by_id(r_empty, "t-novelty")
    prior = independent_tokens(empty["prior_art"][0]["text"])
    bloom = next(i for i in empty["ideas"] if i["id"] == "b1")
    bloom_j = independent_jaccard(independent_tokens(bloom["text"]), prior)
    dup = next(i for i in empty["ideas"] if i["id"] == "a1")
    dup_j = independent_jaccard(independent_tokens(dup["text"]), prior)
    if not (dup_j == 1.0 and bloom_j < 0.5):
        return fail(f"jaccard fixture broken dup={dup_j} bloom={bloom_j}")
    bloom_row = next(x for x in nov["ideas"] if x["id"] == "b1")
    dup_row = next(x for x in nov["ideas"] if x["id"] == "a1")
    if bloom_row["novel"] is not True or dup_row["novel"] is not False:
        return fail(f"novelty labels bloom={bloom_row} dup={dup_row}")
    if nov.get("pass") is not True:
        return fail("novelty min_novel_count=1 must PASS (bloom idea)")

    d_cl = result_by_id(r_cl, "t-diversity")
    d_sp = result_by_id(r_sp, "t-diversity")
    sim_cl = independent_simpson(independent_counts(clustered["ideas"], cats))
    sim_sp = independent_simpson(independent_counts(spread["ideas"], cats))
    if not (sim_cl < 0.4 <= sim_sp):
        return fail(f"simpson clustered={sim_cl} spread={sim_sp}")
    if abs(d_cl["simpson"] - sim_cl) > 1e-6:
        return fail(f"diversity clustered mismatch {d_cl['simpson']} vs {sim_cl}")
    if abs(d_sp["simpson"] - sim_sp) > 1e-6:
        return fail(f"diversity spread mismatch {d_sp['simpson']} vs {sim_sp}")
    if d_cl.get("pass") is not False:
        return fail("clustered diversity must FAIL min_simpson=0.4")
    if d_sp.get("pass") is not True:
        return fail("spread diversity must PASS min_simpson=0.4")
    if not (d_cl["simpson"] < d_sp["simpson"]):
        return fail("clustered simpson must be < spread simpson (same n=10)")

    obj_ok = result_by_id(r_empty, "t-objection")
    obj_miss = result_by_id(r_miss, "t-objection")
    if len(empty["objections"]) != 2:
        return fail("empty-gamma objection fixture count")
    if obj_ok.get("pass") is not True or obj_ok.get("count") != 2:
        return fail(f"objection known-pass {obj_ok}")
    if obj_miss.get("pass") is not False:
        return fail(f"objection known-fail on empty list {obj_miss}")

    ev_ok = result_by_id(r_empty, "t-evidence")
    ev_miss = result_by_id(r_miss, "t-evidence")
    if ev_ok.get("pass") is not True or ev_ok.get("count") != 2:
        return fail(f"evidence known-pass {ev_ok}")
    if ev_miss.get("pass") is not False:
        return fail(f"evidence known-fail {ev_miss}")

    cx_ok = result_by_id(r_empty, "t-counterexample")
    cx_miss = result_by_id(r_miss, "t-counterexample")
    if cx_ok.get("pass") is not True or cx_ok.get("count") != 1:
        return fail(f"counterexample known-pass {cx_ok}")
    if cx_miss.get("pass") is not False:
        return fail(f"counterexample known-fail {cx_miss}")

    payload = {
        "probe": "probe1-known-answers",
        "unit_id": "IMP-0301",
        "pass": True,
        "kinds_checked": sorted(required),
        "independent_empty_gamma_counts": ind_empty,
        "coverage_empty_gamma_pass": cov.get("pass"),
        "coverage_full_pass": cov_full.get("pass"),
        "aggregate_would_pass_on_empty_gamma": cov.get("aggregate_would_pass"),
        "simpson_clustered": d_cl["simpson"],
        "simpson_spread": d_sp["simpson"],
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:IMP-0301-probe1 each non-count target type has a known-answer fixture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
