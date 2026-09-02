#!/usr/bin/env python3
"""Probe 2: fused workflow worse than every source is rejected (FC-11333).

Regression seed from TST-0233 / spec 11333. Independent of the gate's
`worse_than_sources.fired` flag: this probe recomputes passed-case scores
from live execute() runs and requires fusion_score < every source score.

Also executes the named complementarity case (case.beta-only): source alpha
fails, fusion.complement succeeds. Per-source matched-case matrices must be
present. Stage-padded fusion must NOT be classified as worse-than-every-source
(both-states for this detector).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from gate import (  # noqa: E402
    FAILURE_WORSE,
    FAILURE_WORSE_ID,
    complementarity_cases,
    evaluate_named,
    execute,
    index_workflows,
    load_corpus,
    score_from_runs,
)

LIB = HERE / "fixtures" / "corpus.json"
NAMED_CASE = "case.beta-only"


def _ok(name: str, cond: bool, detail: str = "") -> bool:
    print(f"{name}={cond}" + (f" {detail}" if detail else ""))
    return bool(cond)


def main() -> int:
    corpus = load_corpus(LIB)
    budget = int(corpus["budget"])
    catalog = index_workflows(corpus)
    cases = {str(c["id"]): c for c in corpus["cases"]}

    degraded = evaluate_named(corpus, "fusion.degraded")
    padded = evaluate_named(corpus, "fusion.padded")
    complement = evaluate_named(corpus, "fusion.complement")

    independent_scores = {}
    for wid in ("fusion.degraded", "wf.alpha", "wf.beta", "fusion.complement", "fusion.padded"):
        runs = [execute(catalog[wid], case, budget) for case in corpus["cases"]]
        independent_scores[wid] = score_from_runs(runs)

    named_case = cases[NAMED_CASE]
    alpha_named = execute(catalog["wf.alpha"], named_case, budget)
    fusion_named = execute(catalog["fusion.complement"], named_case, budget)
    comps_vs_alpha = complementarity_cases(complement["fusion"], complement["sources"][0])
    comps_vs_beta = complementarity_cases(complement["fusion"], complement["sources"][1])

    print(
        json.dumps(
            {
                "probe": "probe2-worse-than-sources",
                "unit_id": "TST-0233",
                "degraded_verdict": degraded["verdict"],
                "degraded_class": degraded["failure_class"],
                "degraded_score": degraded["fusion"]["score"],
                "alpha_score": independent_scores["wf.alpha"],
                "beta_score": independent_scores["wf.beta"],
                "padded_worse_fired": padded["worse_than_sources"]["fired"],
                "complement_verdict": complement["verdict"],
                "named_case": NAMED_CASE,
                "alpha_named_passed": alpha_named["passed"],
                "fusion_named_passed": fusion_named["passed"],
                "matrix": degraded["matrix"],
            },
            sort_keys=True,
        )
    )

    degraded_indep = independent_scores["fusion.degraded"]
    alpha_indep = independent_scores["wf.alpha"]
    beta_indep = independent_scores["wf.beta"]

    checks = [
        (
            "degraded_rejected",
            degraded["verdict"] == "REJECT",
            f"verdict={degraded['verdict']}",
        ),
        (
            "named_worse_class",
            degraded["failure_class"] == FAILURE_WORSE
            and degraded["failure_class_id"] == FAILURE_WORSE_ID,
            f"class={degraded['failure_class']!r} id={degraded['failure_class_id']!r}",
        ),
        (
            "independent_worse_than_every_source",
            degraded_indep < alpha_indep and degraded_indep < beta_indep,
            f"fusion={degraded_indep} alpha={alpha_indep} beta={beta_indep}",
        ),
        (
            "gate_score_matches_independent",
            degraded["fusion"]["score"] == degraded_indep
            and complement["fusion"]["score"] == independent_scores["fusion.complement"]
            and padded["fusion"]["score"] == independent_scores["fusion.padded"],
            "",
        ),
        (
            "matrix_has_every_source",
            set(degraded["matrix"]) >= {"fusion.degraded", "wf.alpha", "wf.beta"},
            f"keys={sorted(degraded['matrix'])}",
        ),
        (
            "padded_not_classified_worse",
            padded["worse_than_sources"]["fired"] is False
            and padded["failure_class"] != FAILURE_WORSE,
            f"worse_fired={padded['worse_than_sources']['fired']} class={padded['failure_class']!r}",
        ),
        (
            "complement_not_classified_worse",
            complement["worse_than_sources"]["fired"] is False
            and complement["verdict"] == "ACCEPT",
            f"verdict={complement['verdict']}",
        ),
        (
            "named_case_alpha_fails",
            alpha_named["passed"] is False and alpha_named["case_id"] == NAMED_CASE,
            f"run={alpha_named}",
        ),
        (
            "named_case_fusion_succeeds",
            fusion_named["passed"] is True
            and fusion_named["case_id"] == NAMED_CASE
            and fusion_named["reason"] == "handled",
            f"run={fusion_named}",
        ),
        (
            "complement_set_names_beta_only_vs_alpha",
            any(c["case_id"] == NAMED_CASE for c in comps_vs_alpha),
            f"vs_alpha={comps_vs_alpha}",
        ),
        (
            "complement_set_nonempty_vs_beta",
            bool(comps_vs_beta),
            f"vs_beta={comps_vs_beta}",
        ),
        (
            "every_source_qualifies_for_complement",
            complement["verdict"] == "ACCEPT"
            and all(r["qualifies"] for r in complement["per_source"]),
            f"per_source={complement['per_source']}",
        ),
        (
            "budget_parity_across_arms",
            degraded["budget_parity"]
            and padded["budget_parity"]
            and complement["budget_parity"]
            and degraded["budget"] == padded["budget"] == complement["budget"] == budget,
            f"budget={budget}",
        ),
        (
            "degraded_outcomes_all_fail",
            degraded["fusion"]["passed"] == 0
            and all(ok is False for _cid, ok in degraded["fusion"]["outcome_vector"]),
            f"vector={degraded['fusion']['outcome_vector']}",
        ),
        (
            "both_states_worse_detector",
            degraded["worse_than_sources"]["fired"] is True
            and padded["worse_than_sources"]["fired"] is False
            and complement["worse_than_sources"]["fired"] is False,
            "",
        ),
    ]

    failed = False
    for name, cond, detail in checks:
        if not _ok(name, cond, detail):
            failed = True
    if failed:
        print("FAILED:TST-0233-probe2 worse-than-every-source detector did not fire cleanly")
        return 1
    print(
        "SUCCESS:TST-0233-probe2 degraded fusion rejected; "
        "named complementarity case executed and differs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
