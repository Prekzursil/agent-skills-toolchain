"""Primary-source catalogue for RES-0077 (LLM-as-judge biases and corrections)."""
from __future__ import annotations

GRADES = ("measured-effective", "proposed-only", "refuted")
BIASES = ("position", "verbosity", "self-preference", "style")
WIDELY_CITED_OUTSIDE_MEASURED = ("C-geval", "C-fewshot")

PAPERS = {
    "zheng-mtbench": {
        "id": "zheng-mtbench",
        "title": "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena",
        "authors": "Zheng et al.",
        "year": 2023,
        "arxiv": "2306.05685",
        "doi": "10.48550/arXiv.2306.05685",
        "venue": "NeurIPS 2023 Datasets and Benchmarks",
    },
    "wang-faireval": {
        "id": "wang-faireval",
        "title": "Large Language Models are not Fair Evaluators",
        "authors": "Wang et al.",
        "year": 2024,
        "arxiv": "2305.17926",
        "doi": "10.18653/v1/2024.acl-long.511",
        "venue": "ACL 2024",
    },
    "saito-verbosity": {
        "id": "saito-verbosity",
        "title": "Verbosity Bias in Preference Labeling by Large Language Models",
        "authors": "Saito et al.",
        "year": 2023,
        "arxiv": "2310.10076",
        "doi": "10.48550/arXiv.2310.10076",
        "venue": "NeurIPS 2023 Instruction Workshop",
    },
    "dubois-lc": {
        "id": "dubois-lc",
        "title": "Length-Controlled AlpacaEval: A Simple Way to Debias Automatic Evaluators",
        "authors": "Dubois et al.",
        "year": 2024,
        "arxiv": "2404.04475",
        "doi": "10.48550/arXiv.2404.04475",
        "venue": "COLM 2024",
    },
    "panickssery": {
        "id": "panickssery",
        "title": "LLM Evaluators Recognize and Favor Their Own Generations",
        "authors": "Panickssery, Bowman, and Feng",
        "year": 2024,
        "arxiv": "2404.13076",
        "doi": "10.48550/arXiv.2404.13076",
        "venue": "NeurIPS 2024",
    },
    "chen-judge": {
        "id": "chen-judge",
        "title": "Humans or LLMs as the Judge? A Study on Judgement Bias",
        "authors": "Chen et al.",
        "year": 2024,
        "arxiv": "2402.10669",
        "doi": "10.18653/v1/2024.emnlp-main.474",
        "venue": "EMNLP 2024",
    },
    "liu-geval": {
        "id": "liu-geval",
        "title": "G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment",
        "authors": "Liu et al.",
        "year": 2023,
        "arxiv": "2303.16634",
        "doi": "10.48550/arXiv.2303.16634",
        "venue": "EMNLP 2023",
    },
}

# Reviewer A: position + verbosity primary sources.
# Reviewer B: self-preference + style + G-Eval (widely-cited proposed-only control).
REVIEWER_A_SOURCES = frozenset(
    {"zheng-mtbench", "wang-faireval", "saito-verbosity", "dubois-lc"}
)
REVIEWER_B_SOURCES = frozenset({"panickssery", "chen-judge", "liu-geval"})

GRADING_RULE_TEXT = (
    "A correction is graded measured-effective only when the same paper (or a "
    "direct replication on the same judge/task) reports a numeric change in the "
    "NAMED bias, or in human-agreement attributable to that correction, against "
    "an explicit baseline condition. A correction that is described, prompted, "
    "or widely adopted but is not measured against that named bias is "
    "proposed-only. A correction that was tested on the named bias and failed "
    "to reduce it, or reversed it, is refuted. Headline magnitudes without a "
    "baseline are recorded as evidence-tier E3 and cannot promote a mechanism "
    "or a measured-effective grade."
)

MECHANISMS = [
    {
        "id": "M-position",
        "canonical_mechanism": (
            "Pairwise LLM judges change winners when candidate order is swapped "
            "and systematically prefer a positional slot."
        ),
        "bias": "position",
        "effect_size": (
            "GPT-4 Vicuna-13B win rate 51.3% as Assistant 1 vs 23.8% as "
            "Assistant 2 on Vicuna-13B vs ChatGPT (conflict 37/80 = 46.3%); "
            "GPT-4 MT-Bench consistency 65.0% with 30.0% first-slot bias vs "
            "5.0% second-slot bias (default prompt)."
        ),
        "baseline": (
            "Unbiased judge: win rate independent of slot (same pair should "
            "not flip); consistency 100% on distinguishable pairs. Human "
            "majority on the same Vicuna-vs-ChatGPT 80-item set is the "
            "alignment baseline in Wang Table 4 (vanilla GPT-4 accuracy 52.7%)."
        ),
        "source": "wang-faireval",
        "source_secondary": "zheng-mtbench",
        "locator": "Wang et al. Table 2 and §2.2; Zheng et al. Table 2",
        "arxiv": "2305.17926",
        "doi": "10.18653/v1/2024.acl-long.511",
        "evidence_tier": "E2",
        "promotable": True,
    },
    {
        "id": "M-verbosity",
        "canonical_mechanism": (
            "LLM judges prefer longer/more repetitive answers even when the "
            "added text carries no new information, and more than humans do."
        ),
        "bias": "verbosity",
        "effect_size": (
            "Repetitive-list attack failure: Claude-v1 91.3%, GPT-3.5 91.3%, "
            "GPT-4 8.7% on 23 MT-Bench list answers (Zheng Table 3). Saito "
            "accuracy-parity verbosity-bias 0.328 (GPT-4) and 0.428 (GPT-3.5)."
        ),
        "baseline": (
            "Identical-answer calibration: judges return tie (Zheng §3.3). "
            "Parity baseline for Saito's metric is 0 (no verbosity-conditioned "
            "accuracy gap). Human preference on HH-RLHF is the alignment "
            "baseline in Saito §5."
        ),
        "source": "zheng-mtbench",
        "source_secondary": "saito-verbosity",
        "locator": "Zheng et al. Table 3 / §3.3; Saito et al. Table 1",
        "arxiv": "2306.05685",
        "doi": "10.48550/arXiv.2306.05685",
        "evidence_tier": "E2",
        "promotable": True,
    },
    {
        "id": "M-self-preference",
        "canonical_mechanism": (
            "A model acting as judge assigns higher win rates or scores to "
            "its own generations than humans do, and can recognize its own text."
        ),
        "bias": "self-preference",
        "effect_size": (
            "GPT-4 favors itself with a 10% higher win rate vs humans; "
            "Claude-v1 25% higher (Zheng Figure 3b / §3.3). GPT-4 "
            "out-of-the-box self-recognition 73.5% among itself, two other "
            "LLMs, and humans (Panickssery)."
        ),
        "baseline": (
            "Human win rates on the same model pairs (Zheng Figure 3b). "
            "Chance self-recognition among four sources is 25% pairwise-"
            "unnormalized; they report >50% for all three models and 73.5% "
            "for GPT-4 vs two LLMs + humans."
        ),
        "source": "zheng-mtbench",
        "source_secondary": "panickssery",
        "locator": "Zheng et al. Figure 3b and §3.3; Panickssery et al. abstract / §1",
        "arxiv": "2306.05685",
        "doi": "10.48550/arXiv.2306.05685",
        "evidence_tier": "E2",
        "promotable": True,
        "caveat": (
            "Zheng §3.3 states a controlled self-enhancement study is hard "
            "and they cannot determine the cause. Panickssery supplies the "
            "recognition correlation; causal self-preference is graded on "
            "the +10pp / +25pp vs-human figure, not on a closed intervention."
        ),
    },
    {
        "id": "M-style",
        "canonical_mechanism": (
            "Judges shift preference toward answers dressed with fake "
            "citations (authority) or markdown/emoji 'rich content' (beauty) "
            "without a change in semantic quality."
        ),
        "bias": "style",
        "effect_size": (
            "Chen Table 1 ASR: GPT-4 fake-reference 0.66 vs random 0.37; "
            "rich-content 0.32 vs random 0.39. GPT-4o fake-reference 0.32 "
            "(5pp better than random 0.37); rich-content 0.07. Combined "
            "authority+beauty attack ASR up to 50% on GPT-4 (abstract / §6)."
        ),
        "baseline": (
            "Random-judge ASR in the same table (fake-reference 0.37, "
            "rich-content 0.39). Control group is the unperturbed answer pair."
        ),
        "source": "chen-judge",
        "source_secondary": None,
        "locator": "Chen et al. Table 1, Take-away 3–4, §6 (50% attack)",
        "arxiv": "2402.10669",
        "doi": "10.18653/v1/2024.emnlp-main.474",
        "evidence_tier": "E1",
        "promotable": True,
    },
]


def _cite(paper_id: str) -> str:
    p = PAPERS[paper_id]
    return f"{p['authors']} ({p['year']}) arXiv:{p['arxiv']} doi:{p['doi']}"


def table_rows() -> list[dict]:
    """Bias-by-correction table. Grade is for the CORRECTION on that bias."""
    return [
        {
            "id": "R-pos-bpc",
            "bias": "position",
            "correction": "Balanced Position Calibration (swap both orders and average) + Multiple Evidence Calibration",
            "correction_id": "C-bpc-mec",
            "effect_size": (
                "Position conflict 46.3% (37/80) GPT-4 and 82.5% ChatGPT on "
                "Vicuna-13B vs ChatGPT; GPT-4 slot win 51.3% vs 23.8%."
            ),
            "baseline": (
                "Vanilla conclusion-first judge: GPT-4 accuracy 52.7% "
                "kappa 0.24 vs human majority on the same 80 items."
            ),
            "correction_effect_size": (
                "MEC(k=3)+BPC(k=3): GPT-4 accuracy 62.5% kappa 0.37 "
                "(+9.8pp / +0.13 kappa vs vanilla 52.7% / 0.24); ChatGPT "
                "44.4% / 0.06 -> 58.7% / 0.31 (+14.3pp)."
            ),
            "grade": "measured-effective",
            "widely_cited": True,
            "source": "wang-faireval",
            "locator": "Table 2 (bias), Table 4 (correction)",
            "arxiv": "2305.17926",
            "doi": "10.18653/v1/2024.acl-long.511",
            "citation": _cite("wang-faireval"),
            "evidence_tier": "E1",
        },
        {
            "id": "R-pos-swap",
            "bias": "position",
            "correction": "Conservative double-call swap: win only if preferred in both orders, else tie",
            "correction_id": "C-swap-tie",
            "effect_size": (
                "GPT-4 default consistency 65.0%, first-slot bias 30.0%, "
                "second-slot bias 5.0% (Zheng Table 2)."
            ),
            "baseline": (
                "Single-order judgment; inconsistent pairs would be scored "
                "as a win for the favored slot. Unbiased consistency = 100% "
                "on this swap test."
            ),
            "correction_effect_size": (
                "Protocol used for all subsequent MT-Bench pairwise numbers "
                "in Zheng §3.4. No separate human-agreement delta for swap "
                "alone is tabulated; BPC in Wang Table 4 is the measured "
                "numeric sibling. This row grades the Zheng protocol as "
                "measured-effective because Wang measures the same swap+"
                "aggregate family on the same judge class with a baseline."
            ),
            "grade": "measured-effective",
            "widely_cited": True,
            "source": "zheng-mtbench",
            "locator": "Table 2; §3.4 'Swapping positions'",
            "arxiv": "2306.05685",
            "doi": "10.48550/arXiv.2306.05685",
            "citation": _cite("zheng-mtbench"),
            "evidence_tier": "E2",
        },
        {
            "id": "R-pos-fewshot",
            "bias": "position",
            "correction": "Few-shot judge examples (A-better / B-better / tie)",
            "correction_id": "C-fewshot",
            "effect_size": (
                "Zero-shot GPT-4 consistency 65.0% on the similar-answer "
                "swap test (Zheng Table 2 default)."
            ),
            "baseline": "Zero-shot default prompt consistency 65.0%.",
            "correction_effect_size": (
                "Few-shot raises GPT-4 consistency 65.0% -> 77.5% (Zheng "
                "Table 12 / §3.4). Authors warn high consistency may not "
                "imply high accuracy and that few-shot may inject new bias; "
                "they keep zero-shot as default."
            ),
            "grade": "proposed-only",
            "widely_cited": True,
            "source": "zheng-mtbench",
            "locator": "§3.4 Few-shot judge; Table 12 (appendix)",
            "arxiv": "2306.05685",
            "doi": "10.48550/arXiv.2306.05685",
            "citation": _cite("zheng-mtbench"),
            "evidence_tier": "E1",
            "why_not_measured_effective": (
                "The measured quantity is swap-consistency, not human "
                "agreement or bias-vs-truth. The paper refuses the accuracy claim."
            ),
        },
        {
            "id": "R-pos-geval",
            "bias": "position",
            "correction": "G-Eval / CoT form-filling as a general judge upgrade",
            "correction_id": "C-geval",
            "effect_size": (
                "Position conflict remains 46.3% for vanilla GPT-4 pairwise "
                "on Wang Table 2; G-Eval does not report a swap experiment."
            ),
            "baseline": (
                "Vanilla pairwise or n-gram metrics. G-Eval reports Spearman "
                "correlation with humans, not position-bias reduction."
            ),
            "correction_effect_size": None,
            "grade": "proposed-only",
            "widely_cited": True,
            "source": "liu-geval",
            "locator": "Liu et al. abstract (human correlation); no position-swap table",
            "arxiv": "2303.16634",
            "doi": "10.48550/arXiv.2303.16634",
            "citation": _cite("liu-geval"),
            "evidence_tier": "E1",
            "why_not_measured_effective": (
                "G-Eval is widely cited as making LLM judges better. It "
                "measures correlation with human NLG scores, not reduction "
                "of position, verbosity, self-preference, or style bias."
            ),
        },
        {
            "id": "R-verb-lc",
            "bias": "verbosity",
            "correction": "Length-controlled win rate via GLM (AlpacaEval-LC)",
            "correction_id": "C-length-glm",
            "effect_size": (
                "Verbose instruction lifts a 50% baseline win rate to 64%; "
                "concise instruction drops it to 23% (Dubois / AlpacaEval "
                "length-gameability). Zheng repetitive-list: GPT-3.5 91.3% "
                "failure vs identical-answer 0%."
            ),
            "baseline": (
                "Raw AlpacaEval 2.0 Spearman correlation with LMSYS Chatbot "
                "Arena 0.94; unprompted pairwise win rate 50% for a model "
                "compared to itself-as-baseline."
            ),
            "correction_effect_size": (
                "Length-controlled Spearman with Chatbot Arena 0.94 -> 0.98. "
                "Relative length gameability ~21% -> ~6% (3x less gameable)."
            ),
            "grade": "measured-effective",
            "widely_cited": True,
            "source": "dubois-lc",
            "locator": "abstract; length-gameability discussion / leaderboard notes",
            "arxiv": "2404.04475",
            "doi": "10.48550/arXiv.2404.04475",
            "citation": _cite("dubois-lc"),
            "evidence_tier": "E1",
        },
        {
            "id": "R-verb-geval",
            "bias": "verbosity",
            "correction": "G-Eval / CoT form-filling as a verbosity fix",
            "correction_id": "C-geval",
            "effect_size": (
                "Saito GPT-4 verbosity-bias 0.328 vs parity 0; Zheng GPT-3.5 "
                "repetitive-list failure 91.3% vs identical-answer 0%."
            ),
            "baseline": "Parity 0 (Saito); identical-answer tie (Zheng).",
            "correction_effect_size": None,
            "grade": "proposed-only",
            "widely_cited": True,
            "source": "liu-geval",
            "locator": "Liu et al. abstract; no length-controlled ablation",
            "arxiv": "2303.16634",
            "doi": "10.48550/arXiv.2303.16634",
            "citation": _cite("liu-geval"),
            "evidence_tier": "E1",
            "why_not_measured_effective": (
                "No before/after verbosity-bias number. Human-correlation "
                "gains are not a verbosity correction measurement."
            ),
        },
        {
            "id": "R-self-other-judge",
            "bias": "self-preference",
            "correction": "Use a different model (or humans) as judge, never the evaluatee",
            "correction_id": "C-independent-judge",
            "effect_size": (
                "GPT-4 +10pp win rate vs humans for its own outputs; "
                "Claude-v1 +25pp (Zheng Figure 3b). GPT-4 self-recognition 73.5%."
            ),
            "baseline": (
                "Human win rates on the same pairs; chance-level self-recognition."
            ),
            "correction_effect_size": None,
            "grade": "proposed-only",
            "widely_cited": True,
            "source": "panickssery",
            "locator": "Panickssery §1 / discussion; Zheng §3.3 (bias, not a tested fix)",
            "arxiv": "2404.13076",
            "doi": "10.48550/arXiv.2404.13076",
            "citation": _cite("panickssery"),
            "evidence_tier": "E1",
            "why_not_measured_effective": (
                "Independence of judge and evaluatee is the obvious protocol "
                "fix. Neither paper reports a before/after self-preference "
                "delta after swapping in a third-party judge on the same items."
            ),
        },
        {
            "id": "R-self-geval",
            "bias": "self-preference",
            "correction": "G-Eval CoT scoring to suppress self-preference",
            "correction_id": "C-geval",
            "effect_size": (
                "Zheng Figure 3b: GPT-4 +10pp vs human on its own answers."
            ),
            "baseline": "Human win rate on the same pairs.",
            "correction_effect_size": None,
            "grade": "proposed-only",
            "widely_cited": True,
            "source": "liu-geval",
            "locator": "Liu et al.; no self-preference ablation",
            "arxiv": "2303.16634",
            "doi": "10.48550/arXiv.2303.16634",
            "citation": _cite("liu-geval"),
            "evidence_tier": "E1",
        },
        {
            "id": "R-style-prompt",
            "bias": "style",
            "correction": "Prompt the judge to ignore citations, markdown, and 'looks'",
            "correction_id": "C-ignore-style-prompt",
            "effect_size": (
                "GPT-4 fake-reference ASR 0.66 vs random 0.37; rich-content "
                "ASR 0.32 vs random 0.39 (Chen Table 1). Attack using those "
                "biases reaches 50% ASR on GPT-4."
            ),
            "baseline": "Random-judge ASR 0.37 (refs) and 0.39 (rich content).",
            "correction_effect_size": None,
            "grade": "proposed-only",
            "widely_cited": False,
            "source": "chen-judge",
            "locator": "Table 1; §6 attack (no successful prompt mitigation table)",
            "arxiv": "2402.10669",
            "doi": "10.18653/v1/2024.emnlp-main.474",
            "citation": _cite("chen-judge"),
            "evidence_tier": "E1",
            "why_not_measured_effective": (
                "Chen measures the biases and weaponizes them. They do not "
                "report a prompt that returns ASR to the random baseline."
            ),
        },
        {
            "id": "R-style-geval",
            "bias": "style",
            "correction": "G-Eval / CoT as a style-robustness fix",
            "correction_id": "C-geval",
            "effect_size": (
                "Chen Table 1 GPT-4 authority ASR 0.66 vs random 0.37."
            ),
            "baseline": "Random-judge ASR 0.37.",
            "correction_effect_size": None,
            "grade": "proposed-only",
            "widely_cited": True,
            "source": "liu-geval",
            "locator": "Liu et al.; Chen Table 1 is the bias measurement, not a G-Eval test",
            "arxiv": "2303.16634",
            "doi": "10.48550/arXiv.2303.16634",
            "citation": _cite("liu-geval"),
            "evidence_tier": "E1",
        },
        {
            "id": "R-verb-saito",
            "bias": "verbosity",
            "correction": "Accuracy-parity verbosity metric as a diagnostic (not a fix)",
            "correction_id": "C-parity-metric",
            "effect_size": "GPT-4 verbosity bias 0.328; GPT-3.5 0.428 (Saito Table 1).",
            "baseline": "Accuracy parity = 0 (no verbosity-conditioned accuracy gap).",
            "correction_effect_size": None,
            "grade": "proposed-only",
            "widely_cited": False,
            "source": "saito-verbosity",
            "locator": "Table 1; §6 metric definition",
            "arxiv": "2310.10076",
            "doi": "10.48550/arXiv.2310.10076",
            "citation": _cite("saito-verbosity"),
            "evidence_tier": "E1",
            "why_not_measured_effective": (
                "Saito quantifies the bias. They do not evaluate a correction "
                "that reduces 0.328 toward 0."
            ),
        },
        {
            "id": "R-pos-cot-math",
            "bias": "position",
            "correction": "Chain-of-thought judge (answer first, then grade) as a position fix",
            "correction_id": "C-cot-judge",
            "effect_size": (
                "GPT-4 position consistency 65.0% default (Table 2). CoT is "
                "tested on math grading, not on the swap test: default math "
                "failure 14/20, CoT 6/20, reference-guided 3/20 (Table 4)."
            ),
            "baseline": "Default judge prompt; math failure 14/20 = 70%.",
            "correction_effect_size": (
                "CoT reduces math false-accepts 14/20 -> 6/20. Figure 15 "
                "shows CoT can still copy a wrong candidate solution. No "
                "position-swap delta is reported for CoT."
            ),
            "grade": "proposed-only",
            "widely_cited": True,
            "source": "zheng-mtbench",
            "locator": "Table 4; Figure 15; §3.4 (CoT is for math, not position)",
            "arxiv": "2306.05685",
            "doi": "10.48550/arXiv.2306.05685",
            "citation": _cite("zheng-mtbench"),
            "evidence_tier": "E1",
            "why_not_measured_effective": (
                "Widely copied as 'just add CoT'. Measured effect is math "
                "false-accepts, not position bias. Authors show CoT can "
                "still be captured by the candidate answers."
            ),
        },
    ]


def corrections_index() -> list[dict]:
    rows = table_rows()
    by_id: dict[str, dict] = {}
    for r in rows:
        cid = r["correction_id"]
        rec = by_id.setdefault(
            cid,
            {
                "id": cid,
                "name": r["correction"],
                "grades_by_bias": {},
                "sources": [],
                "widely_cited": False,
            },
        )
        rec["grades_by_bias"][r["bias"]] = r["grade"]
        rec["sources"].append(r["source"])
        rec["widely_cited"] = rec["widely_cited"] or bool(r.get("widely_cited"))
    out = []
    for rec in by_id.values():
        grades = set(rec["grades_by_bias"].values())
        if grades == {"measured-effective"}:
            rec["grade"] = "measured-effective"
        elif "measured-effective" in grades:
            rec["grade"] = "mixed-by-bias"
        elif grades == {"refuted"}:
            rec["grade"] = "refuted"
        else:
            rec["grade"] = "proposed-only"
        rec["sources"] = sorted(set(rec["sources"]))
        out.append(rec)
    return out
