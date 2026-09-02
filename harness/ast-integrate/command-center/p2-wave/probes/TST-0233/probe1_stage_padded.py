#!/usr/bin/env python3
"""Probe 1: stage-padded fusion with identical behaviour is rejected.

Detector control from TST-0233: submit a fusion that only adds noop stages
and confirm rejection. Both-states: a fusion that has more stages AND
different (complementary) behaviour is accepted. Extra noops on an already
complementary fusion must not flip it to REJECT.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from gate import (  # noqa: E402
    FAILURE_MORE_STAGES,
    FAILURE_MORE_STAGES_ID,
    evaluate_named,
    index_workflows,
    load_corpus,
    plant_noop_stages,
    run_workflow,
    score_from_runs,
    stage_count,
)

LIB = HERE / "fixtures" / "corpus.json"
NAMED_COMPLEMENT_CASE = "case.beta-only"


def _ok(name: str, cond: bool, detail: str = "") -> bool:
    print(f"{name}={cond}" + (f" {detail}" if detail else ""))
    return bool(cond)


def main() -> int:
    corpus = load_corpus(LIB)
    budget = int(corpus["budget"])
    catalog = index_workflows(corpus)
    cases = corpus["cases"]

    padded = evaluate_named(corpus, "fusion.padded")
    complement = evaluate_named(corpus, "fusion.complement")
    alpha = run_workflow(catalog["wf.alpha"], cases, budget)
    beta = run_workflow(catalog["wf.beta"], cases, budget)

    dynamic = plant_noop_stages(catalog["wf.alpha"], n=3)
    dynamic["sources"] = ["wf.alpha", "wf.beta"]
    from gate import evaluate_admission  # local import after corpus load

    dynamic_decision = evaluate_admission(
        dynamic, [catalog["wf.alpha"], catalog["wf.beta"]], cases, budget
    )

    complement_padded = plant_noop_stages(catalog["fusion.complement"], n=3)
    complement_padded["sources"] = ["wf.alpha", "wf.beta"]
    complement_padded_decision = evaluate_admission(
        complement_padded, [catalog["wf.alpha"], catalog["wf.beta"]], cases, budget
    )

    vanity_would_rank_padded = (
        padded["fusion"]["score"] + padded["fusion"]["n_stages"]
        > alpha["score"] + alpha["n_stages"]
        and padded["fusion"]["score"] == alpha["score"]
    )

    alpha_fail_beta_case = [
        r for r in alpha["runs"] if r["case_id"] == NAMED_COMPLEMENT_CASE
    ]
    fusion_on_beta_case = [
        r for r in complement["fusion"]["runs"] if r["case_id"] == NAMED_COMPLEMENT_CASE
    ]

    print(
        json.dumps(
            {
                "probe": "probe1-stage-padded",
                "unit_id": "TST-0233",
                "padded_verdict": padded["verdict"],
                "padded_class": padded["failure_class"],
                "complement_verdict": complement["verdict"],
                "padded_stages": padded["fusion"]["n_stages"],
                "alpha_stages": alpha["n_stages"],
                "padded_score": padded["fusion"]["score"],
                "alpha_score": alpha["score"],
                "dynamic_verdict": dynamic_decision["verdict"],
                "complement_plus_noops_verdict": complement_padded_decision["verdict"],
            },
            sort_keys=True,
        )
    )

    checks = [
        (
            "padded_rejected",
            padded["verdict"] == "REJECT",
            f"verdict={padded['verdict']}",
        ),
        (
            "named_more_stages_class",
            padded["failure_class"] == FAILURE_MORE_STAGES
            and padded["failure_class_id"] == FAILURE_MORE_STAGES_ID,
            f"class={padded['failure_class']!r} id={padded['failure_class_id']!r}",
        ),
        (
            "identical_behavior_to_alpha",
            padded["fusion"]["outcome_vector"] == alpha["outcome_vector"],
            f"padded={padded['fusion']['outcome_vector']} alpha={alpha['outcome_vector']}",
        ),
        (
            "more_stages_than_alpha",
            padded["fusion"]["n_stages"] > alpha["n_stages"],
            f"padded={padded['fusion']['n_stages']} alpha={alpha['n_stages']}",
        ),
        (
            "score_ignores_stage_count",
            padded["fusion"]["score"] == alpha["score"]
            and padded["fusion"]["score_formula"] == "passed_cases"
            and padded["stage_count_is_scoring_component"] is False,
            f"padded_score={padded['fusion']['score']} alpha_score={alpha['score']}",
        ),
        (
            "vanity_metric_would_prefer_padding",
            vanity_would_rank_padded,
            "passed+n_stages ranks padded above alpha; gate must not",
        ),
        (
            "complement_accepted_despite_more_stages",
            complement["verdict"] == "ACCEPT"
            and complement["fusion"]["n_stages"] > alpha["n_stages"]
            and complement["fusion"]["n_stages"] > beta["n_stages"]
            and complement["fusion"]["outcome_vector"] != alpha["outcome_vector"],
            f"verdict={complement['verdict']} stages={complement['fusion']['n_stages']}",
        ),
        (
            "dynamic_pad_of_alpha_rejected",
            dynamic_decision["verdict"] == "REJECT"
            and dynamic_decision["failure_class"] == FAILURE_MORE_STAGES,
            f"verdict={dynamic_decision['verdict']} class={dynamic_decision['failure_class']!r}",
        ),
        (
            "complement_plus_noops_still_accepted",
            complement_padded_decision["verdict"] == "ACCEPT"
            and complement_padded_decision["failure_class"] is None,
            f"verdict={complement_padded_decision['verdict']}",
        ),
        (
            "budget_parity",
            padded["budget_parity"] is True
            and complement["budget_parity"] is True
            and padded["budget"] == complement["budget"] == budget,
            f"budget={budget}",
        ),
        (
            "independent_score_matches_matrix",
            score_from_runs(padded["fusion"]["runs"]) == padded["fusion"]["score"]
            and score_from_runs(alpha["runs"]) == alpha["score"],
            "",
        ),
        (
            "stage_count_helper_agrees",
            stage_count(catalog["fusion.padded"]) == padded["fusion"]["n_stages"] == 5,
            f"n={padded['fusion']['n_stages']}",
        ),
        (
            "named_complement_case_differs_on_good_fusion",
            bool(alpha_fail_beta_case)
            and alpha_fail_beta_case[0]["passed"] is False
            and bool(fusion_on_beta_case)
            and fusion_on_beta_case[0]["passed"] is True,
            f"alpha={alpha_fail_beta_case} fusion={fusion_on_beta_case}",
        ),
        (
            "both_states_discriminate",
            padded["verdict"] == "REJECT" and complement["verdict"] == "ACCEPT",
            "",
        ),
    ]

    failed = False
    for name, cond, detail in checks:
        if not _ok(name, cond, detail):
            failed = True
    if failed:
        print("FAILED:TST-0233-probe1 stage-padded fusion not rejected cleanly")
        return 1
    print("SUCCESS:TST-0233-probe1 stage-padded fusion rejected; complementary fusion accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
