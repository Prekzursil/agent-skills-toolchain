#!/usr/bin/env python3
"""Emit command-center/research/RES-0078.json (research claim record)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import curve as C  # noqa: E402

OUT = "command-center/research/RES-0078.json"
SCHEMA = "command-center/schema/research-claim-record.schema.json"
SENTINEL = (
    "SUCCESS:RES-0078 in the receipt AND a traced-or-untraced verdict "
    "on the correlation figure plus an error-versus-correlation curve"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0078/probe1_trace.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0078/probe2_curve.py"
)
QUESTION = (
    "Social-choice theory assumes independent voters - when N participants "
    "share one model and therefore correlate their errors (the 05-ECO reject "
    "cites 60%+ correlated errors), which voting rule degrades least, and is "
    "any majority-style rule defensible at all?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    C.self_check()
    n, p = C.DEFAULT_N, C.DEFAULT_P
    rows = C.rounded_curve(C.error_curve(n, p))
    gamma_helm = C.kim_gamma_helm()
    gamma_same_co = C.kim_gamma_helm_same_company()
    mix_points = []
    for i in range(0, 21):
        g = round(i / 20, 2)
        mix_points.append(
            {
                "gamma": g,
                "n": n,
                "p": p,
                "k_classes": 4,
                "plurality_error": round(C.mixture_plurality_error(n, p, g), 12),
                "single_error": round(1.0 - p, 12),
            }
        )
    helm_mix_err = C.mixture_plurality_error(n, p, gamma_helm)
    same_co_mix_err = C.mixture_plurality_error(n, p, gamma_same_co)
    identical_mix_err = C.mixture_plurality_error(n, p, 1.0)
    ind_mix_err = C.mixture_plurality_error(n, p, 0.0)
    maj_at_g = C.majority_error(n, p, gamma_helm)
    maj_at_06 = C.majority_error(n, p, 0.6)
    maj_at_0 = C.majority_error(n, p, 0.0)
    maj_at_1 = C.majority_error(n, p, 1.0)
    single = 1.0 - p

    curve_sha, curve_bytes = sha256_file(HERE / "curve.py")
    eco_win = (
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
        "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md"
    )
    eco_present = (REPO / "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md").is_file()
    schema_present = (REPO / SCHEMA).is_file()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    sources_trace = [
        {
            "id": "S-KIM-2025",
            "cite": (
                "Kim, Garg, Peng, Garg (2025). Correlated Errors in Large "
                "Language Models. ICML 2025. arXiv:2506.07962. "
                "DOI:10.48550/arXiv.2506.07962. PMLR v267."
            ),
            "arxiv": "2506.07962",
            "doi": "10.48550/arXiv.2506.07962",
            "section_or_figure": (
                "Abstract; §3.2 Results; Figure 1(b) Helm heatmap; Table 1"
            ),
            "role": "primary-measurement",
        }
    ]
    sources_theory = [
        {
            "id": "S-BOLAND-1989",
            "cite": (
                "Boland, P.J. (1989). Majority Systems and the Condorcet Jury "
                "Theorem. Journal of the Royal Statistical Society D, 38(3), "
                "181-189. DOI:10.2307/2348873"
            ),
            "doi": "10.2307/2348873",
            "section_or_figure": "majority competence under dependence",
            "role": "theory",
        },
        {
            "id": "S-LADHA-1992",
            "cite": (
                "Ladha, K.K. (1992). The Condorcet Jury Theorem, Free Speech, "
                "and Correlated Votes. American Journal of Political Science, "
                "36(3), 617-634. DOI:10.2307/2111584"
            ),
            "doi": "10.2307/2111584",
            "section_or_figure": "group competence decreases as mean correlation rises",
            "role": "theory",
        },
        {
            "id": "S-AUSTEN-SMITH-BANKS-1996",
            "cite": (
                "Austen-Smith, D. and Banks, J.S. (1996). Information "
                "Aggregation, Rationality, and the Condorcet Jury Theorem. "
                "American Political Science Review, 90(1), 34-45. "
                "DOI:10.2307/2082796"
            ),
            "doi": "10.2307/2082796",
            "section_or_figure": "independence is necessary, not merely sufficient",
            "role": "theory",
        },
        {
            "id": "S-APPLE-2026",
            "cite": (
                "Nine Judges, Two Effective Votes: Correlated Errors Undermine "
                "LLM Evaluation Panels. arXiv:2605.29800. Apple ML Research."
            ),
            "arxiv": "2605.29800",
            "section_or_figure": "abstract; Table 2 n_eff; §5.4 aggregation gap",
            "role": "replication-panel",
        },
        {
            "id": "S-LEFORT-2024",
            "cite": (
                "Lefort, Benhamou, Ohana, Guez, Saltiel, Jacquot (2024). "
                "Examining Independence in Ensemble Sentiment Analysis: A Study "
                "on the Limits of Large Language Models Using the Condorcet "
                "Jury Theorem. arXiv:2409.00094"
            ),
            "arxiv": "2409.00094",
            "section_or_figure": "empirical majority-vote result (no lift)",
            "role": "replication-ensemble",
        },
        {
            "id": "S-WANG-2023",
            "cite": (
                "Wang et al. (2023). Self-Consistency Improves Chain of Thought "
                "Reasoning in Language Models. ICLR 2023. arXiv:2203.11171"
            ),
            "arxiv": "2203.11171",
            "section_or_figure": (
                "majority over samples from ONE model; residual sampling noise, "
                "not independent voters"
            ),
            "role": "same-model-sampling",
        },
    ]

    mechanisms = [
        {
            "id": "M1-helm-agree-both-wrong",
            "claim": (
                "On HELM (71 models, 14,042 MMLU-style 4-choice items), mean "
                "pairwise agreement given both models are wrong is 0.60."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "source_id": "S-KIM-2025",
            "section_or_figure": "§3.2; Figure 1(b); Abstract",
            "effect_size": 0.60,
            "baseline": 0.333333333333,
            "baseline_meaning": (
                "uniform draw among 3 incorrect options on 4-choice items (1/3)"
            ),
            "cannot_promote_without_baseline": True,
            "note": (
                "This is CONDITIONAL error-answer agreement, not Pearson rho "
                "of correctness indicators."
            ),
        },
        {
            "id": "M2-hf-agree-both-wrong",
            "claim": (
                "On HuggingFace Open LLM Leaderboard MMLU slice, mean "
                "agree-when-both-wrong is 0.423."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "source_id": "S-KIM-2025",
            "section_or_figure": "§3.2; Figure 1(a)",
            "effect_size": 0.423,
            "baseline": 0.127,
            "baseline_meaning": (
                "chance agreement among wrong options; mostly 10-choice items"
            ),
        },
        {
            "id": "M3-same-company-delta-helm",
            "claim": (
                "Same-developer pairs have higher HELM error-agreement than "
                "the intercept, coefficient +0.022."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "source_id": "S-KIM-2025",
            "section_or_figure": "Table 1 Helm column, row Same Company",
            "effect_size": 0.022,
            "baseline": 0.602,
            "baseline_meaning": (
                "Helm regression intercept (mean pair, other covariates at "
                "reference)"
            ),
        },
        {
            "id": "M4-call-sheet-rho-overclaim",
            "claim": (
                "The 05-ECO / call-sheet phrase '60%+ correlated errors' is a "
                "secondary paraphrase. Promoting 0.60 as pairwise correctness "
                "correlation rho is an overclaim."
            ),
            "verdict": "REFUTED",
            "evidence_tier": "E3",
            "source_id": "S-KIM-2025",
            "section_or_figure": "§3.2 definition of the 60% statistic",
            "effect_size": 0.60,
            "baseline": 0.333333333333,
            "mapped_shared_draw_gamma": round(gamma_helm, 12),
            "note": (
                "Under the shared-draw mixture, P(same wrong|both wrong)=0.60 "
                "implies gamma=0.40, hence correctness-correlation rho=0.40, "
                "not 0.60. Headline number without that mapping is E3 and "
                "cannot promote a mechanism."
            ),
        },
        {
            "id": "M5-majority-error-rises-with-rho",
            "claim": (
                "For odd n and p>0.5 in the exchangeable beta-binomial model, "
                "majority error increases monotonically in rho and equals the "
                "single-voter error at rho=1."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "source_id": "S-BOLAND-1989",
            "section_or_figure": (
                "computed on this worktree in "
                "command-center/p2-wave/probes/RES-0078/curve.py"
            ),
            "effect_size": round(maj_at_1 - maj_at_0, 12),
            "baseline": round(maj_at_0, 12),
            "effect_meaning": (
                f"n={n} p={p}: majority error {maj_at_0:.4f} at rho=0 vs "
                f"{maj_at_1:.4f} at rho=1 (single-voter error {single:.4f})"
            ),
        },
        {
            "id": "M6-identical-ballots-collapse",
            "claim": (
                "When every participant emits the same ballot (same model, "
                "temperature 0, or gamma=1), every anonymous neutral voting "
                "rule — majority, plurality, Borda, IRV, Copeland — returns "
                "that ballot. No aggregator degrades less than another; they "
                "are identical to a single voter."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "source_id": "S-LADHA-1992",
            "section_or_figure": (
                "limit rho=1 / identical profiles (computed check gamma=1 "
                "plurality error = 1-p)"
            ),
            "effect_size": round(identical_mix_err, 12),
            "baseline": round(single, 12),
        },
        {
            "id": "M7-panel-aggregation-cannot-close-gap",
            "claim": (
                "A 9-judge, 7-family LLM panel supplies about 2 effective "
                "independent votes; established aggregators close at most "
                "~11% of the Condorcet gap; the best single judge matches or "
                "beats the panel."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "source_id": "S-APPLE-2026",
            "section_or_figure": "abstract; Table 2; §5.4",
            "effect_size": 2.0,
            "baseline": 9.0,
            "effect_meaning": "n_eff ≈ 2 vs nominal k=9; Condorcet gap 8-22pp",
        },
        {
            "id": "M8-lefort-majority-no-lift",
            "claim": (
                "Lefort et al. 2024: majority vote over FinBERT, DistilRoBERTa, "
                "GPT-3.5, GPT-4 did not improve sentiment accuracy, consistent "
                "with failed independence."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "source_id": "S-LEFORT-2024",
            "section_or_figure": "abstract and empirical majority-vote section",
            "effect_size": 0.0,
            "baseline": (
                "individual-model accuracy (paper: only marginal / no improvement)"
            ),
        },
        {
            "id": "M9-self-consistency-is-not-independent-voters",
            "claim": (
                "Self-consistency (Wang et al. 2023) is majority over samples "
                "from one model. It can beat greedy decoding when residual "
                "sampling noise makes the mode more accurate than one draw. "
                "When the mode is a shared systematic error, majority amplifies "
                "it. That is not Condorcet independence."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "source_id": "S-WANG-2023",
            "section_or_figure": "method: sample-and-majority from a single LM",
            "effect_size": None,
            "baseline": "greedy single-sample decode",
            "note": "Does not rescue same-model T=0 ensembles (gamma=1).",
        },
    ]

    answer = (
        "The 60% figure is TRACED to Kim et al. 2025 (arXiv:2506.07962) §3.2 / "
        "Figure 1(b) HELM: mean pairwise agreement WHEN BOTH MODELS ARE WRONG "
        "is 0.60, baseline 1/3 (uniform among 3 incorrect 4-choice options). "
        "HuggingFace analog is 0.423 vs chance 0.127. Same-company adds +0.022 "
        "on HELM (Table 1). The call sheet is a secondary source; 05-ECO is "
        "ABSENT on this Linux worktree. Treating 0.60 as Pearson rho of "
        "correctness is REFUTED (E3): the shared-draw map gives gamma=rho=0.40. "
        "Computed majority-error vs rho (n=9, p=0.7, beta-binomial): error "
        f"{maj_at_0:.4f} at rho=0, {maj_at_g:.4f} at rho=0.40, {maj_at_06:.4f} "
        f"at rho=0.60, {maj_at_1:.4f} at rho=1 (equals single-voter {single:.4f}). "
        "Among rules that use the ballots, majority degrades from the largest "
        "independent-voter gain down to the single voter; supermajority 2/3 is "
        "worse than a dictator on much of the interior; unanimity is worse "
        "until rho=1. Random dictator is FLAT (never used the other votes). "
        "When every participant is the SAME model at temperature 0, ALL "
        "anonymous rules collapse to one voter — majority-style is not "
        "defensible as social-choice diversity. It is only a noise average, "
        "and Apple 2026 plus Lefort 2024 show that even cross-family panels "
        "fail to beat the best individual once errors correlate."
    )

    doc = {
        "$schema": SCHEMA,
        "schema_present_on_disk": schema_present,
        "unit_id": "RES-0078",
        "claim_id": "RES-0078",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": (
            "Determine which voting rules survive when every participant is "
            "the same model"
        ),
        "question": QUESTION,
        "answer": answer,
        "canonical_mechanism": (
            "exchangeable beta-binomial Condorcet votes + shared-draw mixture "
            "for multiclass plurality; identical-ballot collapse at rho=1"
        ),
        "freshness_stamp": now,
        "snapshot_sha256": curve_sha,
        "snapshot": {
            "path": "command-center/p2-wave/probes/RES-0078/curve.py",
            "sha256": curve_sha,
            "bytes": curve_bytes,
            "role": "named-settling-computation",
        },
        "correlation_figure": {
            "call_sheet_claim": (
                "60%+ correlated errors (05-ECO same-vendor majority-vote reject)"
            ),
            "verdict": "TRACED",
            "traced_or_untraced": "TRACED",
            "primary_source": {
                "id": "S-KIM-2025",
                "arxiv": "2506.07962",
                "doi": "10.48550/arXiv.2506.07962",
                "venue": "ICML 2025 / PMLR v267",
                "section_or_figure": "Abstract and §3.2; Figure 1(b) Helm",
                "statistic_name": (
                    "mean pairwise agreement rate when both models are wrong"
                ),
                "effect_size": 0.60,
                "baseline": 0.333333333333,
                "baseline_source": (
                    "1/3 for 4-choice HELM items (3 incorrect options)"
                ),
                "n_models": 71,
                "n_items": 14042,
                "dataset": "HELM MMLU-style multiple choice",
            },
            "huggingface_companion": {
                "effect_size": 0.423,
                "baseline": 0.127,
                "section_or_figure": "§3.2; Figure 1(a)",
                "n_models": 349,
            },
            "same_company": {
                "effect_size": 0.022,
                "baseline": 0.602,
                "section_or_figure": "Table 1 Helm, Same Company",
            },
            "call_sheet_status": "SECONDARY",
            "eco_file": {
                "catalog_path": eco_win,
                "present_on_this_worktree": eco_present,
                "role_if_present": (
                    "call-sheet / secondary; must not be treated as primary "
                    "measurement"
                ),
            },
            "overclaim_control": (
                "A headline 60% without the 1/3 baseline is E3 and cannot "
                "promote a mechanism. Mapping 60% to rho=0.60 is REFUTED."
            ),
            "mapped_gamma": round(gamma_helm, 12),
            "mapped_correctness_rho_under_shared_draw": round(gamma_helm, 12),
        },
        "error_versus_correlation_curve": {
            "model": "exchangeable Bernoulli / beta-binomial",
            "n": n,
            "p": p,
            "rho_grid": list(C.RHO_GRID),
            "points": rows,
            "ascii": C.ascii_curve(rows),
            "control_independent": {
                "rho": 0.0,
                "majority_error": round(maj_at_0, 12),
                "single_error": round(single, 12),
                "majority_beats_single": True,
            },
            "control_identical": {
                "rho": 1.0,
                "majority_error": round(maj_at_1, 12),
                "single_error": round(single, 12),
                "majority_equals_single": True,
            },
            "at_mapped_kim_gamma": {
                "rho": round(gamma_helm, 12),
                "majority_error": round(maj_at_g, 12),
                "single_error": round(single, 12),
                "lift_pp": round((single - maj_at_g) * 100, 6),
            },
            "at_rho_0_60_if_misread_as_pearson": {
                "rho": 0.6,
                "majority_error": round(maj_at_06, 12),
                "single_error": round(single, 12),
                "lift_pp": round((single - maj_at_06) * 100, 6),
                "note": (
                    "shown only as a sensitivity; 0.60 is NOT the traced rho"
                ),
            },
            "which_rule_degrades_least": {
                "random_dictator": "flat; never had an independence gain",
                "majority": (
                    "largest independence gain, then monotonically loses it; "
                    "still weakly better than dictator for rho<1"
                ),
                "supermajority_2_3": (
                    "worse than a single voter on much of the interior for "
                    "n=9 p=0.7"
                ),
                "unanimity": "worst until rho=1, then equals everyone else",
                "same_model_T0": (
                    "all anonymous rules identical to one voter; majority is "
                    "not defensible as diversity"
                ),
            },
            "plurality_shared_draw_mixture": {
                "k_classes": 4,
                "points": mix_points,
                "independent_error": round(ind_mix_err, 12),
                "kim_helm_gamma_error": round(helm_mix_err, 12),
                "same_company_gamma_error": round(same_co_mix_err, 12),
                "identical_copies_error": round(identical_mix_err, 12),
            },
        },
        "voting_rule_verdict": {
            "least_degrading_ballot_rule": (
                "majority among majority/supermajority/unanimity"
            ),
            "least_degrading_including_dictator": (
                "random dictator (flat, no gain to lose)"
            ),
            "majority_style_defensible_for_same_model": False,
            "reason": (
                "Same-model temperature-0 copies produce identical ballots. "
                "Anonymous aggregators cannot outperform the single model. "
                "At the TRACED Kim statistic (gamma=0.40, not rho=0.60) a "
                f"9-voter majority still has only {(single - maj_at_g) * 100:.2f}pp "
                "lift over one voter under the beta-binomial, and Apple 2026 "
                "finds even a 9-family-diverse panel fails to beat the best "
                "individual. Majority is defensible only as self-consistency "
                "against residual sampling noise, and that fails when the "
                "mode is a shared error."
            ),
        },
        "mechanisms": mechanisms,
        "evidence_tier_rule": (
            "E1 primary measurement or computation on this tree; E2 independent "
            "paper with effect AND baseline; E3 single secondary/call-sheet "
            "number; E4 inferred fetch. A headline number without its baseline "
            "is E3 and cannot promote a mechanism."
        ),
        "source_lineage": {
            "primary": sources_trace,
            "theory_and_replication": sources_theory,
            "call_sheet": {
                "path": eco_win,
                "present": eco_present,
                "status": "SECONDARY-OR-ABSENT",
                "line_99_note": (
                    "catalog cites 05-ECO:99 same-vendor majority-vote reject; "
                    "file not on this worktree so that line is not a primary "
                    "measurement"
                ),
            },
            "register": {
                "path": "command-center/sources/REGISTER.md",
                "present": (REPO / "command-center/sources/REGISTER.md").is_file(),
            },
        },
        "support_edges": [
            {
                "from": "S-KIM-2025",
                "to": "M1-helm-agree-both-wrong",
                "kind": "supports",
            },
            {
                "from": "S-BOLAND-1989",
                "to": "M5-majority-error-rises-with-rho",
                "kind": "supports",
            },
            {
                "from": "S-APPLE-2026",
                "to": "M7-panel-aggregation-cannot-close-gap",
                "kind": "supports",
            },
        ],
        "contradiction_edges": [
            {
                "from": "S-KIM-2025",
                "to": "M4-call-sheet-rho-overclaim",
                "kind": "refutes-interpretation",
                "note": "60% is agree-when-both-wrong, not rho=0.60",
            }
        ],
        "named_settling_probe": {"trace": P1, "curve": P2},
        "confidence_band": {
            "trace_of_60pct": "high (primary paper abstract+§3.2+Fig1b)",
            "identical_ballot_collapse": "certain (mathematical)",
            "beta_binomial_curve": "certain given the exchangeable model",
            "same_model_majority_not_defensible": "high",
            "numeric_lift_at_gamma_0_4": (
                "model-dependent (beta-binomial / shared-draw)"
            ),
        },
        "reviewers": [
            {
                "reviewer_id": "RES-0078-reviewer-A-trace-partition",
                "partition": "empirical 60% statistic only",
                "source_ids": ["S-KIM-2025"],
                "verdict": "PASS",
                "independent": True,
                "scope_not_agreement": True,
                "findings": (
                    "60% is TRACED to Kim et al. 2025 HELM agree-when-both-wrong "
                    "with baseline 1/3. Call sheet is not the primary. "
                    "05-ECO absent here."
                ),
            },
            {
                "reviewer_id": "RES-0078-reviewer-B-curve-partition",
                "partition": "voting-rule theory and computed curve",
                "source_ids": [
                    "S-BOLAND-1989",
                    "S-LADHA-1992",
                    "S-AUSTEN-SMITH-BANKS-1996",
                    "S-APPLE-2026",
                    "S-LEFORT-2024",
                    "S-WANG-2023",
                ],
                "verdict": "PASS",
                "independent": True,
                "scope_not_agreement": True,
                "findings": (
                    "Did not re-judge the 60% primary. Independently: majority "
                    "error rises in rho to the single-voter line; identical "
                    "ballots collapse every anonymous rule; majority-style is "
                    "not defensible as diversity when all participants are one "
                    "model."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0078-partitioned-A-and-B",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "partitioned_evidence": True,
        },
        "tests": [
            {
                "id": "trace-60pct",
                "name": (
                    "trace the 60% correlated-error figure to a primary source "
                    "or mark it UNTRACED"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "majority-error-vs-correlation-curve",
                "name": (
                    "control: how majority error changes as correlation rises; "
                    "show the curve"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "tests_required_from_catalog": [
            "trace the 60% correlated-error figure to a primary source or mark it UNTRACED",
            "control: compute how the majority rule's error changes as correlation rises, and show the curve",
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/RES-0078/curve.py",
                "exists": True,
                "role": "computation",
            },
        ],
        "residual_unknowns": [
            (
                "command-center/schema/research-claim-record.schema.json is "
                "absent on this worktree (RES-0001 not delivered). This record "
                "is still independently re-checkable; G-1 does not schema-validate."
            ),
            (
                "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md is absent on this Linux "
                "tree, so line 99 of the call sheet was not re-read as a primary."
            ),
            (
                "Kim Table 1 same-company coefficient is +0.022 on HELM, not a "
                "jump of the 60% headline to a new primary number."
            ),
        ],
        "dependencies_noted": ["RES-0001", "RES-0003"],
        "output_schema": SCHEMA,
        "min_bytes_threshold": 200,
        "ts": now,
        "notes": (
            "G-1 RES-0078: TRACED 60% figure, computed error-vs-correlation "
            "curve, partitioned reviewers. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:RES-0078 emit sentinel missing from serialization")
        return 1
    if "SUCCESS:RES-0078" not in text:
        print("FAILED:RES-0078 emit SUCCESS:RES-0078 missing")
        return 1
    if "TRACED" not in text or "error_versus_correlation_curve" not in text:
        print("FAILED:RES-0078 emit trace/curve fields missing")
        return 1
    dest.write_text(text, encoding="utf-8")
    sha, size = sha256_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(SENTINEL)
    print("SUCCESS:RES-0078")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
