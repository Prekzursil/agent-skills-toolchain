#!/usr/bin/env python3
"""Frozen OA literature corpus for WFA-0025.

Every reported_value is a substring of quote. Rounding or paraphrasing a
number is treated as fabrication. Retrieval is recorded; probes re-check
the substring rule, they do not re-fetch the network.
"""
from __future__ import annotations

# Seven named protocol families from the catalog question.
PROTOCOL_IDS = (
    "debate",
    "delphi",
    "verifier-in-the-loop",
    "execution-consensus",
    "best-of-n",
    "self-consistency",
    "role-committees",
)

CORPUS: list[dict] = [
    {
        "protocol_id": "debate",
        "protocol_name": "debate",
        "question_family": "debate",
        "primary": {
            "paper_id": "arXiv:2305.14325",
            "title": (
                "Improving Factuality and Reasoning in Language Models "
                "through Multiagent Debate"
            ),
            "authors": "Du, Yilun; Li, Shuang; Torralba, Antonio; Tenenbaum, Joshua B.; Mordatch, Igor",
            "year": 2023,
            "url": "https://arxiv.org/abs/2305.14325",
            "venue": "preprint",
            "dataset": "GSM8K (100-problem subset; Grade School Math column of Table 1)",
            "metric": "accuracy (%)",
            "baseline_value": "77.0 ± 4.2",
            "reported_value": "85.0 ± 3.5",
            "delta_verbatim": "85.0 ± 3.5",
            "anchor": "Table 1, Multi-Agent (Debate) row, Grade School Math column",
            "quote": (
                "Table 1: Multiagent Debate Improves Reasoning Multi-agent debate "
                "improves the reasoning abilities of language models. Multi-agent "
                "results in the table are run with 3 agents and two rounds of debate. "
                "| Single Agent | 67.0 ± 4.7 | 77.0 ± 4.2 | 91.4 ± 10.6 | "
                "| Multi-Agent (Debate) | 81.8 ± 2.3 | 85.0 ± 3.5 | 122.9 ± 7.6 |"
            ),
            "limitations_verbatim": (
                "To evaluate the GSM8K task, we evaluated the accuracy at which "
                "models were able to obtain the final correct answer, as extracted "
                "from a box. We evaluated models on one hundred grade school math "
                "problems."
            ),
        },
        "independent_signals": [
            {
                "role": "contradiction",
                "independent": True,
                "paper_id": "arXiv:2502.08788",
                "title": (
                    "Stop Overvaluing Multi-Agent Debate -- We Must Rethink "
                    "Evaluation and Embrace Model Heterogeneity"
                ),
                "url": "https://arxiv.org/abs/2502.08788",
                "anchor": "abstract / opening empirical claim (36 scenarios)",
                "quote": (
                    "none of these MAD methods achieve a win rate higher than 20% "
                    "when compared to CoT across 36 scenarios (4 models × 9 benchmarks)"
                ),
                "reported_value": "win rate higher than 20%",
            },
            {
                "role": "contradiction",
                "independent": True,
                "paper_id": "arXiv:2311.17371",
                "title": (
                    "Should we be going MAD? A Look at Multi-Agent Debate "
                    "Strategies for LLMs"
                ),
                "url": "https://arxiv.org/abs/2311.17371",
                "anchor": "abstract",
                "quote": (
                    "multi-agent debating systems, in their current form, do not "
                    "reliably outperform other proposed prompting strategies, such "
                    "as self-consistency and ensembling using multiple reasoning paths"
                ),
                "reported_value": (
                    "do not reliably outperform other proposed prompting strategies, "
                    "such as self-consistency"
                ),
            },
        ],
        "negative_hunt": {
            "queries": [
                "multi-agent debate does not outperform chain-of-thought",
                "MAD underperform self-consistency negative result",
                "\"multi-agent debate\" \"do not reliably outperform\"",
            ],
            "retrieved_negative_count": 2,
            "retrieved_positive_count": 1,
            "note": (
                "Hunt used negative phrasing. Du et al. is one confirmatory signal; "
                "Smit et al. and Zhang et al. are independent and contradict a "
                "general 'debate beats a single well-prompted model' claim."
            ),
        },
        "settling_experiment": None,
    },
    {
        "protocol_id": "delphi",
        "protocol_name": "delphi",
        "question_family": "delphi",
        "primary": {
            "paper_id": "Rowe-Wright-1999-IJF",
            "title": "The Delphi technique as a forecasting tool: issues and analysis",
            "authors": "Rowe, Gene; Wright, George",
            "year": 1999,
            "url": "https://doi.org/10.1016/S0169-2070(99)00018-7",
            "venue": "International Journal of Forecasting 15(4)",
            "dataset": None,
            "metric": None,
            "baseline_value": None,
            "reported_value": None,
            "delta_verbatim": None,
            "anchor": "review article (OA full text not held on this worktree)",
            "quote": None,
            "measured_effect_recorded": False,
            "quote_status": "OA-FULL-TEXT-NOT-HELD",
            "note": (
                "Classic Delphi is in-scope. This sweep did not copy a numeric "
                "task-success delta because OA full text was not held. Recorded "
                "UNQUANTIFIED rather than paraphrased. A rounded invention would "
                "be a fabrication risk under tests_required."
            ),
        },
        "independent_signals": [
            {
                "role": "method-origin",
                "independent": True,
                "paper_id": "Dalkey-Helmer-1963",
                "title": (
                    "An experimental application of the Delphi method to the "
                    "use of experts"
                ),
                "url": "https://doi.org/10.1287/mnsc.9.3.458",
                "anchor": "citation-only on this worktree (paywalled)",
                "quote": None,
                "reported_value": None,
                "note": "Second source exists; numeric delta not copied.",
            }
        ],
        "negative_hunt": {
            "queries": [
                "Delphi no more accurate than unstructured interacting groups",
                "Delphi herding accuracy worse across rounds",
                "\"Delphi\" \"does not outperform\" structured group",
            ],
            "retrieved_negative_count": 1,
            "retrieved_positive_count": 1,
            "note": (
                "Secondary abstracts report mixed findings: Delphi often beats "
                "unstructured groups but is not consistently superior to other "
                "structured procedures. No OA numeric delta copied."
            ),
        },
        "settling_experiment": (
            "Obtain OA or licensed full text of Rowe & Wright 1999 (or Dalkey "
            "RAND RM-5888) and copy one verbatim accuracy/round table cell; "
            "until then Delphi remains UNQUANTIFIED, not a paraphrased percent."
        ),
    },
    {
        "protocol_id": "verifier-in-the-loop",
        "protocol_name": "verifier-in-the-loop",
        "question_family": "verifier-in-the-loop",
        "primary": {
            "paper_id": "arXiv:2110.14168",
            "title": "Training Verifiers to Solve Math Word Problems",
            "authors": (
                "Cobbe, Karl; Kosaraju, Vineet; Bavarian, Mohammad; Chen, Mark; "
                "Jun, Heewoo; Kaiser, Lukasz; Plappert, Matthias; Tworek, Jerry; "
                "Hilton, Jacob; Nakano, Reiichiro; Hesse, Christopher; Schulman, John"
            ),
            "year": 2021,
            "url": "https://arxiv.org/abs/2110.14168",
            "venue": "preprint",
            "dataset": "GSM8K (full test; 100 completions ranked by verifier)",
            "metric": "solve rate vs finetuned generator (size-equivalent boost)",
            "baseline_value": "finetuned 175B model",
            "reported_value": (
                "6B verification slightly outperforms a finetuned 175B model"
            ),
            "delta_verbatim": "boost approximately equivalent to a 30x model size increase",
            "anchor": "Conclusion, arXiv:2110.14168",
            "quote": (
                "On the full dataset, 6B verification slightly outperforms a "
                "finetuned 175B model, thereby offering a boost approximately "
                "equivalent to a 30x model size increase."
            ),
            "measured_effect_recorded": True,
        },
        "independent_signals": [
            {
                "role": "replication",
                "independent": True,
                "paper_id": "arXiv:2305.20050",
                "title": "Let's Verify Step by Step",
                "url": "https://arxiv.org/abs/2305.20050",
                "anchor": "abstract + Best-of-1860 table (PRM vs ORM)",
                "quote": (
                    "We use our state-of-the-art PRM to solve 78.2% of problems "
                    "from a representative subset of the MATH test set."
                ),
                "reported_value": "78.2%",
            }
        ],
        "negative_hunt": {
            "queries": [
                "verifier reward model overoptimization best-of-n fails",
                "process supervision does not outperform outcome supervision",
                "\"verification\" GSM8K \"does not\" outperform finetuning",
            ],
            "retrieved_negative_count": 1,
            "retrieved_positive_count": 2,
            "note": (
                "Lightman et al. also report majority voting at 69.6% vs PRM "
                "78.2% at Best-of-1860 — majority is weaker, not a null of "
                "verification. Gao et al. document BoN overoptimization as the "
                "failure mode when the reward model is exploited."
            ),
        },
        "settling_experiment": None,
    },
    {
        "protocol_id": "execution-consensus",
        "protocol_name": "execution-consensus",
        "question_family": "execution-consensus",
        "primary": {
            "paper_id": "arXiv:2203.07814",
            "title": "Competition-Level Code Generation with AlphaCode",
            "authors": "Li, Yujia et al. (DeepMind)",
            "year": 2022,
            "url": "https://arxiv.org/abs/2203.07814",
            "venue": "Science / preprint",
            "dataset": (
                "Codeforces simulated contests with more than 5,000 participants"
            ),
            "metric": "average ranking (top-x%)",
            "baseline_value": None,
            "reported_value": "top 54.3%",
            "delta_verbatim": "top 54.3%",
            "anchor": "abstract, arXiv:2203.07814",
            "quote": (
                "AlphaCode achieved on average a ranking of top 54.3% in "
                "competitions with over 5,000 participants."
            ),
            "measured_effect_recorded": True,
        },
        "independent_signals": [],
        "negative_hunt": {
            "queries": [
                "AlphaCode replication fails Codeforces ranking",
                "execution filter clustering does not improve pass@k",
                "\"CodeT\" independent replication execution consensus",
            ],
            "retrieved_negative_count": 0,
            "retrieved_positive_count": 1,
            "note": (
                "CodeT / AlphaCode 2 are related execution-filter systems; this "
                "sweep did not copy a second unaffiliated lab's Codeforces top-x% "
                "figure, so the 54.3% statistic remains SINGLE-SOURCE."
            ),
        },
        "settling_experiment": (
            "Unaffiliated lab re-evaluation of sample-then-execute-then-cluster "
            "on a post-cutoff Codeforces contest with >5000 participants, "
            "reporting the same top-x% ranking metric."
        ),
    },
    {
        "protocol_id": "best-of-n",
        "protocol_name": "best-of-n",
        "question_family": "best-of-n",
        "primary": {
            "paper_id": "arXiv:2305.20050",
            "title": "Let's Verify Step by Step",
            "authors": (
                "Lightman, Hunter; Kosaraju, Vineet; Burda, Yura; Edwards, Harri; "
                "Baker, Bowen; Lee, Teddy; Leike, Jan; Schulman, John; "
                "Sutskever, Ilya; Cobbe, Karl"
            ),
            "year": 2023,
            "url": "https://arxiv.org/abs/2305.20050",
            "venue": "ICLR 2024 / preprint",
            "dataset": "MATH representative subset; Best-of-1860",
            "metric": "% solved (Best-of-1860)",
            "baseline_value": "69.6",
            "reported_value": "78.2",
            "delta_verbatim": "78.2",
            "anchor": "Best-of-1860 table: ORM 72.4 / PRM 78.2 / Majority Voting 69.6",
            "quote": (
                "ORM PRM Majority Voting % Solved (Best-of-1860) 72.4 78.2 69.6. "
                "We use our state-of-the-art PRM to solve 78.2% of problems from "
                "a representative subset of the MATH test set."
            ),
            "measured_effect_recorded": True,
        },
        "independent_signals": [
            {
                "role": "replication",
                "independent": True,
                "paper_id": "arXiv:2110.14168",
                "title": "Training Verifiers to Solve Math Word Problems",
                "url": "https://arxiv.org/abs/2110.14168",
                "anchor": "test-time protocol: sample 100, rank with verifier",
                "quote": (
                    "At test time, we sample 100 completions to each test problem, "
                    "rank them with the verifier, and then return the one with the "
                    "highest verifier score."
                ),
                "reported_value": "sample 100 completions",
            }
        ],
        "negative_hunt": {
            "queries": [
                "best-of-n reward model overoptimization Gao 2023",
                "best-of-n does not improve as N increases",
                "\"Best-of-N\" \"overoptimization\"",
            ],
            "retrieved_negative_count": 1,
            "retrieved_positive_count": 2,
            "note": (
                "Cobbe Fig 7(a) records 6B verifier performance decreasing beyond "
                "400 completions: search eventually finds adversarial solutions "
                "that fool the verifier."
            ),
        },
        "settling_experiment": None,
    },
    {
        "protocol_id": "self-consistency",
        "protocol_name": "self-consistency",
        "question_family": "self-consistency",
        "primary": {
            "paper_id": "arXiv:2203.11171",
            "title": (
                "Self-Consistency Improves Chain of Thought Reasoning in "
                "Language Models"
            ),
            "authors": (
                "Wang, Xuezhi; Wei, Jason; Schuurmans, Dale; Le, Quoc; Chi, Ed; "
                "Narang, Sharan; Chowdhery, Aakanksha; Zhou, Denny"
            ),
            "year": 2022,
            "url": "https://arxiv.org/abs/2203.11171",
            "venue": "ICLR 2023",
            "dataset": "GSM8K",
            "metric": "accuracy (%) PaLM-540B CoT vs self-consistency",
            "baseline_value": "56.5",
            "reported_value": "74.4 (+17.9)",
            "delta_verbatim": "74.4 (+17.9)",
            "anchor": "Table 1 PaLM-540B row, GSM8K column, arXiv:2203.11171",
            "quote": (
                "self-consistency boosts the performance of chain-of-thought "
                "prompting with a striking margin on a range of popular arithmetic "
                "and commonsense reasoning benchmarks, including GSM8K (+17.9%). "
                "PaLM-540B CoT-prompting 56.5 Self-consistency 74.4 (+17.9)"
            ),
            "measured_effect_recorded": True,
        },
        "independent_signals": [
            {
                "role": "replication",
                "independent": True,
                "paper_id": "arXiv:2305.20050",
                "title": "Let's Verify Step by Step",
                "url": "https://arxiv.org/abs/2305.20050",
                "anchor": "Best-of-1860 Majority Voting column",
                "quote": (
                    "ORM PRM Majority Voting % Solved (Best-of-1860) 72.4 78.2 69.6"
                ),
                "reported_value": "69.6",
            }
        ],
        "negative_hunt": {
            "queries": [
                "self-consistency does not improve chain of thought",
                "majority vote hurts accuracy GSM8K",
                "\"self-consistency\" negative result reasoning",
            ],
            "retrieved_negative_count": 0,
            "retrieved_positive_count": 2,
            "note": (
                "No OA independent null of self-consistency on GSM8K was copied. "
                "Lightman majority 69.6% on MATH is a weaker BoN baseline, not a "
                "null of Wang et al. on GSM8K."
            ),
        },
        "settling_experiment": None,
    },
    {
        "protocol_id": "role-committees",
        "protocol_name": "role-committees",
        "question_family": "role-committees",
        "primary": {
            "paper_id": "arXiv:2308.00352",
            "title": (
                "MetaGPT: Meta Programming for A Multi-Agent Collaborative "
                "Framework"
            ),
            "authors": "Hong, Sirui; Zhuge, Mingchen; et al.",
            "year": 2023,
            "url": "https://arxiv.org/abs/2308.00352",
            "venue": "ICLR 2024",
            "dataset": "HumanEval (Pass@1) and MBPP (Pass@1)",
            "metric": "Pass@1",
            "baseline_value": "67%",
            "reported_value": "85.9%",
            "delta_verbatim": "85.9%",
            "anchor": "abstract + HumanEval discussion, arXiv:2308.00352v7",
            "quote": (
                "Notably, in code generation benchmarks, MetaGPT achieves a new "
                "state-of-the-art (SoTA) with 85.9% and 87.7% in Pass@1. We use "
                "the GPT-4’s 67% HumanEval score (OpenAI 2023) as our baseline"
            ),
            "measured_effect_recorded": True,
        },
        "independent_signals": [],
        "negative_hunt": {
            "queries": [
                "MetaGPT HumanEval 85.9 replication fail",
                "role assignment multi-agent does not improve Pass@1",
                "\"SOP\" multi-agent \"does not outperform\" GPT-4 HumanEval",
            ],
            "retrieved_negative_count": 0,
            "retrieved_positive_count": 1,
            "note": (
                "ChatDev/CAMEL are related role-playing systems, not a "
                "re-measurement of MetaGPT's 85.9% Pass@1. No independent "
                "reimplementation of the SOP committee on HumanEval was copied."
            ),
        },
        "settling_experiment": (
            "Independent re-run of SOP role committee (product manager, "
            "architect, engineer) on HumanEval Pass@1 with a GPT-4-class model "
            "from a different vendor/checkpoint than Hong et al."
        ),
    },
]


def protocol_by_id(pid: str) -> dict:
    for row in CORPUS:
        if row["protocol_id"] == pid:
            return row
    raise KeyError(pid)
