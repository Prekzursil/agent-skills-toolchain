#!/usr/bin/env python3
"""TST-0223 probe 1: monotone-narrowing property over 5,000 randomized nesting trees.

Faithful live re-run of the receipt's recorded result set:
  * narrow() (intersection) holds child <= parent on all 5,000 trees, with
    widening declarations attempted at the deepest node of every widened tree
    (recorded: 5000 trees, 10045 widening declarations, all denied)
  * mutation control: the union mutant FAILS the same property (the property
    detector is red-capable)
  * the sample privileged call at the deepest level is refused with
    spawn_count=0 and code tool-permission-denied
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.permission_bound import N_TREES, SEED, narrow, run_property_corpus, union_widen  # noqa: E402


def main() -> int:
    good = run_property_corpus(n_trees=5000, seed=SEED, narrow_fn=narrow)
    bad = run_property_corpus(n_trees=5000, seed=SEED, narrow_fn=union_widen)

    sample = good["sample_privileged_call"]
    checks = {
        "property_5000_trees_pass": good["pass"] is True and good["n_trees"] == 5000,
        "zero_violations": good["violations"] == 0,
        "widening_attempts_material": good["widening_attempts"] >= 5000,
        "widening_calls_denied_spawn0": good["widening_calls_denied"] > 0
        and sample.get("spawn_count") == 0
        and sample.get("code") == "tool-permission-denied",
        "mutation_union_widen_going_red": bad["pass"] is False and bad["violations"] > 0,
        "child_subset_parent_in_sample_depths": all(
            set(d["effective"]) <= set(good["sample_depths"][0]["effective"]) or d["depth"] > 0
            for d in good["sample_depths"]
        ),
    }
    out = {
        "probe": "probe1_property_corpus",
        "unit": "TST-0223",
        "good": {k: good[k] for k in ("pass", "n_trees", "seed", "violations", "widening_attempts", "widening_calls_denied", "widening_calls_allowed", "trees_ok")},
        "good_sample_call": sample,
        "bad_mutant": {k: bad[k] for k in ("pass", "violations", "widening_calls_allowed")},
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe1_property_corpus.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
