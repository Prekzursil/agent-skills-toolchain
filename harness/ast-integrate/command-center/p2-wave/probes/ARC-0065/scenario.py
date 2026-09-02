"""Both-states measurement of maximal-hybrid duplicate control planes.

Singular A1-only and A2-only tables have zero duplicate classes.
Maximal union (keep A1 and A2) has duplicate classes, including skills.
Split-brain fixture: different skill ids on each plane, drift > 0.
Agree fixture: same skill id on both planes, drift = 0, still duplicates
(consistency today is not singularity).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compose as C  # noqa: E402

SPLIT_A1 = HERE / "fixtures/split/a1"
SPLIT_A2 = HERE / "fixtures/split/a2/REGISTRY.json"
AGREE_A1 = HERE / "fixtures/agree/a1"
AGREE_A2 = HERE / "fixtures/agree/a2/REGISTRY.json"


def _dup_count(architectures: tuple[str, ...]) -> tuple[int, dict[str, list[str]], list[dict[str, Any]]]:
    table = C.extract_table(architectures)
    dups = C.duplicate_classes(table)
    return len(dups), dups, table


def run_scenario() -> dict[str, Any]:
    present = C.missing_source_dossiers()
    a1_only_n, a1_only_dups, a1_table = _dup_count(("A1",))
    a2_only_n, a2_only_dups, a2_table = _dup_count(("A2",))
    max_n, max_dups, max_table = _dup_count(("A1", "A2", "A6"))
    pair = C.adjacent_named_pair(max_table)

    a1_split = C.load_a1_ids(SPLIT_A1)
    a2_split_ids = C.load_a2_skill_ids(SPLIT_A2)
    split = C.split_brain(list(a1_split["loaded_ids"]), a2_split_ids)

    a1_agree = C.load_a1_ids(AGREE_A1)
    a2_agree_ids = C.load_a2_skill_ids(AGREE_A2)
    agree = C.split_brain(list(a1_agree["loaded_ids"]), a2_agree_ids)

    best_single_n = min(a1_only_n, a2_only_n)
    # Best single drift is 0: one plane cannot disagree with a second plane.
    cmp_split = C.compare_objective(max_n, split["drift_count"], best_single_n, 0)
    cmp_agree = C.compare_objective(max_n, agree["drift_count"], best_single_n, 0)

    skills_auths = sorted(
        {r["authority"] for r in max_table if r["capability"] == C.NAMED_CAPABILITY}
    )

    ok = (
        present["A1"]
        and present["A2"]
        and present["A6"]
        and not present["A9"]
        and a1_only_n == 0
        and a2_only_n == 0
        and max_n >= 1
        and C.NAMED_CAPABILITY in max_dups
        and skills_auths == [C.NAMED_A, C.NAMED_B]
        and len(pair) == 2
        and pair[0]["authority"] == C.NAMED_A
        and pair[1]["authority"] == C.NAMED_B
        and a1_split["ok"] is True
        and not a1_split["errors"]
        and not a1_split["warnings"]
        and split["drift_count"] >= 1
        and agree["drift_count"] == 0
        and cmp_split["hybrid_worse"] is True
        and cmp_split["hybrid_confirmed"] is False
        and cmp_agree["hybrid_worse"] is True
        and cmp_agree["hybrid_confirmed"] is False
    )

    return {
        "pass": ok,
        "a9_design_present": present["A9"],
        "source_dossiers_present": present,
        "a1_only_duplicate_class_count": a1_only_n,
        "a2_only_duplicate_class_count": a2_only_n,
        "best_single_duplicate_class_count": best_single_n,
        "maximal_duplicate_class_count": max_n,
        "maximal_duplicate_classes": max_dups,
        "maximal_table": max_table,
        "a1_only_table_rows": len(a1_table),
        "a2_only_table_rows": len(a2_table),
        "named_pair": pair,
        "skills_authorities": skills_auths,
        "split": split,
        "agree": agree,
        "a1_split_silent": not a1_split["errors"] and not a1_split["warnings"],
        "comparison_split": cmp_split,
        "comparison_agree": cmp_agree,
        "hybrid_worse_than_best_single": cmp_split["hybrid_worse"],
        "hybrid_confirmed_better": cmp_split["hybrid_confirmed"],
    }


def main() -> int:
    run = run_scenario()
    printable = {k: v for k, v in run.items() if k not in {"maximal_table", "named_pair"}}
    print(json.dumps(printable, sort_keys=True, default=str))
    if not run.get("pass"):
        print("FAILED:ARC-0065 scenario did not reproduce overlapping planes")
        return 1
    print("SUCCESS:ARC-0065 scenario overlapping-authority pair reproduced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
