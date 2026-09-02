#!/usr/bin/env python3
"""RES-0089 detector table: FPR or UNMEASURED, effect + baseline, no promotion without both."""
from __future__ import annotations

from typing import Any

SENTINEL = (
    "SUCCESS:RES-0089 in the receipt AND a detector table with "
    "false-positive rates or UNMEASURED marks, plus one applied result"
)

# Partitioned evidence: reviewer A and B get disjoint paper ids.
PARTITION_A = frozenset({"oren-2024", "shi-2024", "carlini-2021", "local-canary-g1"})
PARTITION_B = frozenset(
    {"roberts-2024", "golchin-2024", "deng-2024", "mirzadeh-2024", "yang-2023"}
)


def _row(**kwargs: Any) -> dict[str, Any]:
    required = (
        "id",
        "family",
        "name",
        "paper_id",
        "arxiv",
        "doi",
        "section_or_figure",
        "effect_size",
        "baseline",
        "false_positive_rate",
        "evidence_tier",
        "may_promote",
        "may_disqualify_a_result",
        "shown_to_work",
        "caveat",
    )
    missing = [k for k in required if k not in kwargs]
    if missing:
        raise ValueError(f"detector row missing {missing}")
    return dict(kwargs)


DETECTORS: list[dict[str, Any]] = [
    _row(
        id="oren-permutation-exchangeability",
        family="held-out-perturbation",
        name="Canonical-order vs shuffled-order likelihood (permutation / sharded rank)",
        paper_id="oren-2024",
        arxiv="2310.17623",
        doi="10.48550/arXiv.2310.17623",
        section_or_figure="Table 1 (controlled 1.4B Wikitext injection); abstract (exact false-positive guarantees)",
        effect_size=(
            "MNLI 1000 examples injected 10 times: permutation p=0.009, "
            "sharded p=1.96e-11"
        ),
        baseline=(
            "Same 1.4B model, 1-duplication injections stay above 0.05 "
            "(BoolQ dup=1: permutation p=0.099, sharded p=0.156; HellaSwag "
            "dup=1: permutation p=0.485, sharded p=0.478)"
        ),
        false_positive_rate="0.05-by-construction",
        fpr_note=(
            "Type I error equals the chosen significance level under the "
            "exchangeability null (no contamination => all orderings equally "
            "likely). Not an empirically fitted FPR on a foreign corpus."
        ),
        evidence_tier="E1",
        may_promote=True,
        may_disqualify_a_result=True,
        shown_to_work=True,
        caveat=(
            "Requires token likelihoods and an exchangeable item order. "
            "Cannot run on this worktree (no model logprob endpoint). "
            "Fails open on non-exchangeable sets (authors heuristically "
            "filter MMLU subsets)."
        ),
    ),
    _row(
        id="shi-mink-prob",
        family="membership-inference",
        name="Min-K% Prob (mean log-likelihood of lowest-k% tokens)",
        paper_id="shi-2024",
        arxiv="2310.16789",
        doi="10.48550/arXiv.2310.16789",
        section_or_figure="Table 1 (AUC on WikiMIA); Appendix Table 6 (TPR@5%FPR); §4.3 k=20",
        effect_size="WikiMIA average AUC 0.72; average TPR@5%FPR 22.2%",
        baseline="Strongest reference-free baseline LOSS/PPL: AUC 0.67; TPR@5%FPR 19.3%",
        false_positive_rate="0.05-operating-point-on-WikiMIA",
        fpr_note=(
            "Table 5 reports TPR at FPR=5% on WikiMIA member/non-member splits. "
            "That 5% is the chosen ROC operating point on WikiMIA, not a Type I "
            "guarantee on a different benchmark. FPR for disqualifying this "
            "program's scores is UNMEASURED."
        ),
        evidence_tier="E1",
        may_promote=True,
        may_disqualify_a_result=False,
        shown_to_work=True,
        caveat=(
            "Needs token probabilities. WikiMIA uses Wikipedia timestamps as "
            "ground truth; that label process does not transfer to this "
            "program's G-1 oracles. Cannot disqualify a result here."
        ),
    ),
    _row(
        id="golchin-guided-instruction",
        family="guided-completion",
        name="Guided instruction completion vs general instruction (Time Travel)",
        paper_id="golchin-2024",
        arxiv="2308.08493",
        doi="10.48550/arXiv.2308.08493",
        section_or_figure="Table 3 overall accuracy vs human partition labels",
        effect_size=(
            "Algorithm 2 GPT-4 ICL: 14/14 (100%) on GPT-4 partitions and "
            "13/14 (92.86%) on GPT-3.5 partitions"
        ),
        baseline=(
            "ChatGPT-Cheat? strict evaluation on GPT-4: 0/14 (0.00%); "
            "Algorithm 1 ROUGE-L on GPT-3.5: 7/14 (50.00%), i.e. chance "
            "on 14 binary partition labels"
        ),
        false_positive_rate="UNMEASURED",
        fpr_note=(
            "Table 3 is partition-level agreement with human labels, not a "
            "per-instance false-positive rate for the GPT-4 ICL judge. The "
            "judge's own FPR is UNMEASURED, so this detector cannot "
            "disqualify a result."
        ),
        evidence_tier="E1",
        may_promote=True,
        may_disqualify_a_result=False,
        shown_to_work=True,
        caveat=(
            "Requires querying the suspect model plus a GPT-4 judge. "
            "Safety filters made ChatGPT-Cheat? unusable on GPT-4 (0/14 strict)."
        ),
    ),
    _row(
        id="roberts-timeline-cutoff",
        family="timeline",
        name="Pre/post training-cutoff pass-rate vs GitHub presence",
        paper_id="roberts-2024",
        arxiv="2310.10628",
        doi="10.48550/arXiv.2310.10628",
        section_or_figure="Table 1 GPT-4 Codeforces Pass Rate; §Results GitHub Presence paragraph",
        effect_size=(
            "GPT-4 Codeforces: GitHub Presence odds ratio 1.045 "
            "(95% CI 1.039-1.051) before cutoff; prose reports ~4.5% odds "
            "increase per log GitHub Presence unit pre-cutoff"
        ),
        baseline=(
            "Same model, post-cutoff: odds ratio 1.000 (95% CI 0.986-1.014), "
            "not significant (Table 1 After column)"
        ),
        false_positive_rate="UNMEASURED",
        fpr_note=(
            "This is a regression association, not a binary detector with a "
            "measured FPR. A significant pre-cutoff slope is evidence of "
            "contamination but cannot disqualify a single benchmark item."
        ),
        evidence_tier="E1",
        may_promote=True,
        may_disqualify_a_result=False,
        shown_to_work=True,
        caveat=(
            "Needs dated items, a published cutoff, and a popularity proxy. "
            "This program's G-1 oracles are not Codeforces-style dated problems."
        ),
    ),
    _row(
        id="deng-ts-guessing",
        family="guided-completion",
        name="Testset Slot Guessing (mask a wrong MC option / unlikely word)",
        paper_id="deng-2024",
        arxiv="2311.09783",
        doi="10.18653/v1/2024.naacl-long.482",
        section_or_figure="Table 3 Question-Multichoice EM; Figure 4 (~100% after fine-tune); §4.2.2 prose",
        effect_size=(
            "Table 3 MMLU Question-Multichoice EM: ChatGPT 0.52, GPT-4 0.57; "
            "Figure 4 fine-tuned-on-MMLU ChatGPT ~100% EM"
        ),
        baseline=(
            "Same Table 3 TruthfulQA EM: ChatGPT 0.12, GPT-4 0.10. "
            "Fully contaminated ChatGPT ~100% EM (Figure 4). The paper "
            "explicitly says the remaining-option candidate list can be "
            "large/infinite, so a 25% 4-way chance baseline is NOT a "
            "number this paper reports and is not used here. "
            "§4.2.2 prose assigns 57% EM to ChatGPT, which matches "
            "Table 3's GPT-4 cell (0.57) not ChatGPT's (0.52); this row "
            "follows Table 3."
        ),
        false_positive_rate="UNMEASURED",
        fpr_note=(
            "Table 3 EM is not a false-positive rate. Format-learning can raise "
            "slot-guessing without item memorization. Cannot disqualify."
        ),
        evidence_tier="E1",
        may_promote=True,
        may_disqualify_a_result=False,
        shown_to_work=True,
        caveat="Needs a multiple-choice test set. This program's G-1 oracles are not MC items.",
    ),
    _row(
        id="mirzadeh-gsm-symbolic",
        family="held-out-perturbation",
        name="Symbolic template re-instantiation (names/numbers) of GSM8K items",
        paper_id="mirzadeh-2024",
        arxiv="2410.05229",
        doi="10.48550/arXiv.2410.05229",
        section_or_figure="§4.1-4.2; Figure 2 dashed GSM8K line; Appendix Table 1 Gemma2-9b-it row",
        effect_size="Gemma2-9b-it GSM-Symbolic 79.1 (±2.99) (Appendix Table 1 Symbolic column)",
        baseline=(
            "Same model, GSM8K 100-template subset 87.0; Symbolic-M1 "
            "(one clause removed) 84.4 (±2.36). Figure 4 is qualitative "
            "on names-only vs numbers; no names-only mean is tabulated "
            "for this model, so none is cited."
        ),
        false_positive_rate="UNMEASURED",
        fpr_note=(
            "A drop on re-instantiated items can be genuine reasoning "
            "fragility rather than contamination (authors discuss both). "
            "Using the drop as a contamination detector has UNMEASURED FPR."
        ),
        evidence_tier="E1",
        may_promote=True,
        may_disqualify_a_result=False,
        shown_to_work=True,
        caveat=(
            "21/25 models sit >1 stddev above the GSM-Symbolic center on the "
            "original 100 GSM8K templates — suggestive, not a disqualifier."
        ),
    ),
    _row(
        id="carlini-extraction-canary",
        family="canary",
        name="Training-data extraction / unique-sequence memorization",
        paper_id="carlini-2021",
        arxiv="2012.07805",
        doi="10.5555/3483845.3483995",
        section_or_figure="§Results: 604/1800 unique memorized; best config 67%; 604/600000 = 0.1%",
        effect_size="Best attack configuration: 67% of inspected candidates are verbatim training examples",
        baseline=(
            "Top-n sampling ranked by raw LM perplexity: 9% memorized; "
            "temperature sampling: 3%. Among 600,000 honest generations, "
            "at least 604 (0.1%) contain memorized text"
        ),
        false_positive_rate="UNMEASURED",
        fpr_note=(
            "67% is precision of ranked candidates after manual+OpenAI "
            "confirmation, not the FPR of a benchmark-contamination "
            "detector. Unique inserted canaries can have FPR near 0 if "
            "the string is not in the clean corpus; that FPR is measured "
            "locally in detector local-canary-g1, not in this paper."
        ),
        evidence_tier="E1",
        may_promote=True,
        may_disqualify_a_result=False,
        shown_to_work=True,
        caveat="Shows memorization exists; does not by itself disqualify a leaderboard score.",
    ),
    _row(
        id="local-canary-g1",
        family="canary",
        name="Unique planted oracle string vs boilerplate (applied to this program's G-1)",
        paper_id="local-canary-g1",
        arxiv="none-local-measurement",
        doi="none-local-measurement",
        section_or_figure="command-center/p2-wave/probes/RES-0089/ngram_canary.py both_states()",
        effect_size="TPR=1.0 on planted fixture (exact match and 3-gram overlap)",
        baseline="TPR=0.0 / FPR=0.0 on clean boilerplate fixture (exact match and 3-gram overlap)",
        false_positive_rate="0.0",
        fpr_note=(
            "Measured on the clean boilerplate control in this probe directory. "
            "Second signal: canary bytes present in planted file, absent in clean file."
        ),
        evidence_tier="E1",
        may_promote=True,
        may_disqualify_a_result=True,
        shown_to_work=True,
        caveat=(
            "Only disqualifies a surface that contains this unique canary. "
            "Does not detect paraphrased leakage or model-weight contamination."
        ),
    ),
    _row(
        id="yang-llm-decontaminator",
        family="held-out-perturbation",
        name="LLM decontaminator (embedding top-k + GPT-4 same-item judge) vs n-gram on rephrased samples",
        paper_id="yang-2023",
        arxiv="2311.04850",
        doi="10.48550/arXiv.2311.04850",
        section_or_figure="Table 5 (MMLU detection F1); Table 2 (Llama-2-13B MMLU 54.8 vs 85.9)",
        effect_size=(
            "LLM decontaminator F1 on MMLU rephrased-English: Algebra 0.960, "
            "Sociology 0.940, US History 0.970 (Table 5). Llama-2-13B MMLU "
            "after 16-epoch fine-tune on rephrased full prompt: 85.9 "
            "(Table 2 / Figure 1)"
        ),
        baseline=(
            "Same Table 5 10-gram F1 = 0.000 on all three rephrased-English "
            "columns (and on rephrased-Chinese); random-detection F1 = 0.500. "
            "Same Table 2 Llama-2-13B original 5-shot MMLU 54.8."
        ),
        false_positive_rate="UNMEASURED",
        fpr_note=(
            "Table 5 reports pair-classification F1, not a Type I rate for "
            "disqualifying a leaderboard score. Cannot disqualify this "
            "program's results."
        ),
        evidence_tier="E1",
        may_promote=True,
        may_disqualify_a_result=False,
        shown_to_work=True,
        caveat=(
            "Needs training-set access plus a GPT-4 judge. The 85.9 figure "
            "is 0-shot after 16-epoch fine-tune on rephrased MMLU; original "
            "54.8 is 5-shot. Shot-count is not matched."
        ),
    ),
]


def validate_table(rows: list[dict[str, Any]] | None = None) -> tuple[bool, str]:
    rows = list(rows if rows is not None else DETECTORS)
    if len(rows) < 6:
        return False, f"too-few-detectors:{len(rows)}"
    for row in rows:
        fpr = row.get("false_positive_rate")
        if not isinstance(fpr, str) or not fpr.strip():
            return False, f"missing-fpr:{row.get('id')}"
        effect = str(row.get("effect_size") or "")
        baseline = str(row.get("baseline") or "")
        if row.get("may_promote") is True:
            if not effect or effect == "HEADLINE-WITHOUT-BASELINE" or not baseline:
                return False, f"promoted-without-baseline:{row.get('id')}"
            if row.get("evidence_tier") == "E3":
                return False, f"e3-promoted:{row.get('id')}"
        if row.get("may_disqualify_a_result") is True:
            if str(fpr).upper() == "UNMEASURED":
                return False, f"disqualify-with-unmeasured-fpr:{row.get('id')}"
        if (not baseline or effect == "HEADLINE-WITHOUT-BASELINE") and row.get(
            "evidence_tier"
        ) != "E3":
            return False, f"headline-not-marked-e3:{row.get('id')}"
        if row.get("evidence_tier") == "E3" and row.get("may_promote") is True:
            return False, f"e3-promoted:{row.get('id')}"
    return True, f"ok detectors={len(rows)}"


def e3_control_row() -> dict[str, Any]:
    """Known-bad fixture: headline number, no baseline, must stay E3/unpromoted."""
    return _row(
        id="e3-headline-only-control",
        family="canary",
        name="control",
        paper_id="control",
        arxiv="none",
        doi="none",
        section_or_figure="none",
        effect_size="HEADLINE-WITHOUT-BASELINE",
        baseline="",
        false_positive_rate="UNMEASURED",
        evidence_tier="E3",
        may_promote=False,
        may_disqualify_a_result=False,
        shown_to_work=False,
        caveat="control",
    )
