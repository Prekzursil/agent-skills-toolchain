#!/usr/bin/env python3
"""Frozen published measurements for RES-0100.

Every accuracy figure carries catalog_size, effect_size, and baseline.
A headline without a baseline is E3 and cannot promote a mechanism.
Partitions are disjoint: reviewer A = retrieval papers; reviewer B =
learned / rule-based / native-PD sources.
"""
from __future__ import annotations

QUESTION = (
    "For selecting the right skill or tool from a large catalog, what selection "
    "accuracy do retrieval-based, rule-based and learned routers achieve in "
    "published measurements, and is the 05-ECO instruction to adopt the NATIVE "
    "progressive-disclosure mechanism rather than build a bespoke retriever "
    "supported by that evidence?"
)

INHERITED_GRADE = (
    "adopt native progressive disclosure; reject a bespoke retriever "
    "(WORK-UNIT-CATALOG.json RES-0100 inputs cite "
    "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md:83-84,100). The named 05-ECO file "
    "is absent from this Linux worktree."
)

SETTLING_COMPARISON = (
    "RES-0101: on THIS estate's live tool inventory, publish a gold routing "
    "task set first, then measure native progressive-disclosure (all "
    "name+description in context) versus a retrieval router versus a learned "
    "router at >=3 catalog sizes, with a control task that must stay correct "
    "at every size."
)

# reviewer A
PART_A = ("gorilla", "toollm", "apibank")
# reviewer B
PART_B = ("toolken", "anytool", "hugginggpt", "native-pd")

FIGURES: list[dict] = [
    {
        "id": "F-GORILLA-TH-GPTINDEX",
        "mechanism": "retrieval-based",
        "partition": "A",
        "family": "gorilla",
        "metric": "AST overall accuracy (Torch Hub)",
        "metric_kind": "selection_and_call_accuracy",
        "effect_size": 61.82,
        "effect_unit": "percent",
        "baseline": 38.70,
        "baseline_label": "GPT-4 0-shot (no retriever) Torch Hub overall",
        "catalog_size": 95,
        "catalog_size_unit": "APIs",
        "catalog_scope": "Torch Hub subset of APIBench",
        "catalog_size_caveat": (
            "Patil et al. intro says 94 TorchHub calls; dataset section says 95; "
            "combined APIBench is stated as 1,645 APIs."
        ),
        "arxiv": "2305.15334",
        "doi": "10.48550/arXiv.2305.15334",
        "section_or_figure": "Table 1, TorchHub overall, Gorilla (GPT-Index) vs GPT-4 (0-shot)",
        "snapshot": "gorilla-2305.15334.ar5iv.html",
        "snapshot_pin": "61.82",
        "evidence_tier": "E1",
        "confidence_band": "HIGH",
        "can_promote": True,
        "notes": "Retriever-aware Gorilla with GPT-Index docs in context.",
    },
    {
        "id": "F-GORILLA-TH-0SHOT",
        "mechanism": "learned",
        "partition": "A",
        "family": "gorilla",
        "metric": "AST overall accuracy (Torch Hub)",
        "metric_kind": "selection_and_call_accuracy",
        "effect_size": 59.13,
        "effect_unit": "percent",
        "baseline": 38.70,
        "baseline_label": "GPT-4 0-shot Torch Hub overall",
        "catalog_size": 95,
        "catalog_size_unit": "APIs",
        "catalog_scope": "Torch Hub subset of APIBench",
        "arxiv": "2305.15334",
        "doi": "10.48550/arXiv.2305.15334",
        "section_or_figure": "Table 1, TorchHub overall, Gorilla (0-shot) vs GPT-4 (0-shot)",
        "snapshot": "gorilla-2305.15334.ar5iv.html",
        "snapshot_pin": "59.13",
        "evidence_tier": "E1",
        "confidence_band": "HIGH",
        "can_promote": True,
        "notes": "Finetuned selector without a test-time retriever. Not native PD.",
    },
    {
        "id": "F-GORILLA-TH-BM25-HURTS",
        "mechanism": "retrieval-based",
        "partition": "A",
        "family": "gorilla",
        "metric": "AST overall accuracy (Torch Hub)",
        "metric_kind": "selection_and_call_accuracy",
        "effect_size": 40.32,
        "effect_unit": "percent",
        "baseline": 59.13,
        "baseline_label": "Gorilla 0-shot Torch Hub overall (no retriever)",
        "catalog_size": 95,
        "catalog_size_unit": "APIs",
        "catalog_scope": "Torch Hub subset of APIBench",
        "arxiv": "2305.15334",
        "doi": "10.48550/arXiv.2305.15334",
        "section_or_figure": "Table 1, TorchHub overall, Gorilla (BM-25) vs Gorilla (0-shot)",
        "snapshot": "gorilla-2305.15334.ar5iv.html",
        "snapshot_pin": "40.32",
        "evidence_tier": "E1",
        "confidence_band": "HIGH",
        "can_promote": True,
        "notes": (
            "A non-optimal retriever can lower accuracy versus no retriever. "
            "Paper text: adding a non-optimal retriever at test time will "
            "sometimes misguide the model."
        ),
    },
    {
        "id": "F-GORILLA-HF-ORACLE",
        "mechanism": "retrieval-based",
        "partition": "A",
        "family": "gorilla",
        "metric": "AST overall accuracy (HuggingFace)",
        "metric_kind": "selection_and_call_accuracy",
        "effect_size": 91.26,
        "effect_unit": "percent",
        "baseline": 19.80,
        "baseline_label": "GPT-4 0-shot HuggingFace overall",
        "catalog_size": 925,
        "catalog_size_unit": "APIs",
        "catalog_scope": "HuggingFace subset of APIBench (top-20 models per domain)",
        "arxiv": "2305.15334",
        "doi": "10.48550/arXiv.2305.15334",
        "section_or_figure": "Table 1, HuggingFace overall, Gorilla (Oracle) vs GPT-4 (0-shot)",
        "snapshot": "gorilla-2305.15334.ar5iv.html",
        "snapshot_pin": "91.26",
        "evidence_tier": "E1",
        "confidence_band": "MEDIUM",
        "can_promote": True,
        "notes": (
            "Oracle retriever, not a deployable retriever. For non-Gorilla models "
            "the paper only checks domain names on HuggingFace, so GPT-4 19.80 is "
            "not a fully comparable AST match."
        ),
    },
    {
        "id": "F-TOOLLLM-NDCG-I1",
        "mechanism": "retrieval-based",
        "partition": "A",
        "family": "toollm",
        "metric": "NDCG@1 on I1 (single-tool instructions)",
        "metric_kind": "retrieval_ranking",
        "effect_size": 84.2,
        "effect_unit": "percent-ndcg",
        "baseline": 18.4,
        "baseline_label": "BM25 NDCG@1 on I1",
        "catalog_size": 16464,
        "catalog_size_unit": "APIs",
        "catalog_scope": "ToolBench RapidAPI pool (16,464 APIs / 3,451 tools)",
        "arxiv": "2307.16789",
        "doi": "10.48550/arXiv.2307.16789",
        "section_or_figure": (
            "ar5iv Table 3 (ICLR 2024 PDF Table 2), I1 NDCG@1, Ours vs BM25"
        ),
        "snapshot": "toollm-2307.16789.ar5iv.html",
        "snapshot_pin": "84.2",
        "evidence_tier": "E1",
        "confidence_band": "HIGH",
        "can_promote": True,
        "notes": (
            "Dense Sentence-BERT API retriever vs BM25. Ada-002 I1 NDCG@1 is 57.5 "
            "as a second baseline. Ranking quality, not end-to-end tool choice."
        ),
    },
    {
        "id": "F-TOOLLLM-NDCG-I1-ADA",
        "mechanism": "retrieval-based",
        "partition": "A",
        "family": "toollm",
        "metric": "NDCG@1 on I1 (single-tool instructions)",
        "metric_kind": "retrieval_ranking",
        "effect_size": 84.2,
        "effect_unit": "percent-ndcg",
        "baseline": 57.5,
        "baseline_label": "OpenAI text-embedding-ada-002 NDCG@1 on I1",
        "catalog_size": 16464,
        "catalog_size_unit": "APIs",
        "catalog_scope": "ToolBench RapidAPI pool (16,464 APIs / 3,451 tools)",
        "arxiv": "2307.16789",
        "doi": "10.48550/arXiv.2307.16789",
        "section_or_figure": (
            "ar5iv Table 3 (ICLR 2024 PDF Table 2), I1 NDCG@1, Ours vs Ada"
        ),
        "snapshot": "toollm-2307.16789.ar5iv.html",
        "snapshot_pin": "57.5",
        "evidence_tier": "E1",
        "confidence_band": "HIGH",
        "can_promote": True,
        "notes": "Same effect as F-TOOLLLM-NDCG-I1 against the embedding baseline.",
    },
    {
        "id": "F-TOOLLLM-PASS-RETRIEVER",
        "mechanism": "retrieval-based",
        "partition": "A",
        "family": "toollm",
        "metric": "ToolEval average pass rate",
        "metric_kind": "end_to_end_pass_rate",
        "effect_size": 67.3,
        "effect_unit": "percent",
        "baseline": 40.2,
        "baseline_label": "ChatGPT ReACT average pass rate (oracle APIs)",
        "catalog_size": 16464,
        "catalog_size_unit": "APIs",
        "catalog_scope": "ToolBench RapidAPI pool",
        "arxiv": "2307.16789",
        "doi": "10.48550/arXiv.2307.16789",
        "section_or_figure": "Table 4, ToolLLaMA DFSDT-Retriever vs ChatGPT ReACT Average Pass",
        "snapshot": "toollm-2307.16789.iclr-pdf.txt",
        "snapshot_pin": "67.3",
        "evidence_tier": "E1",
        "confidence_band": "MEDIUM",
        "can_promote": False,
        "notes": (
            "Pass rate is not selection accuracy. ToolEval is a ChatGPT judge "
            "(87.1% human agreement on pass rate). AnyTool later shows this "
            "protocol can inflate pass rate when the retriever returns junk."
        ),
    },
    {
        "id": "F-APIBANK-RETRIEVE-CALL",
        "mechanism": "retrieval-based",
        "partition": "A",
        "family": "apibank",
        "metric": "Retrieve+Call correctness (GPT-4)",
        "metric_kind": "selection_and_call_accuracy",
        "effect_size": 37.04,
        "effect_unit": "percent",
        "baseline": 63.66,
        "baseline_label": "GPT-4 Call correctness when the API is given (no retrieval)",
        "catalog_size": 73,
        "catalog_size_unit": "APIs",
        "catalog_scope": "API-Bank runnable evaluation system",
        "arxiv": "2304.08244",
        "doi": "10.48550/arXiv.2304.08244",
        "section_or_figure": "Table 3, GPT-4 Retrieve+Call vs Call",
        "snapshot": "apibank-2304.08244.ar5iv.html",
        "snapshot_pin": "37.04%",
        "evidence_tier": "E1",
        "confidence_band": "HIGH",
        "can_promote": True,
        "notes": (
            "At catalog size 73, forcing retrieval drops GPT-4 from 63.66% Call "
            "to 37.04% Retrieve+Call. GPT-3.5-turbo Retrieve+Call is 38.52% "
            "against Call 59.40%."
        ),
    },
    {
        "id": "F-APIBANK-GPT35-RETRIEVE-CALL",
        "mechanism": "retrieval-based",
        "partition": "A",
        "family": "apibank",
        "metric": "Retrieve+Call correctness (GPT-3.5-turbo)",
        "metric_kind": "selection_and_call_accuracy",
        "effect_size": 38.52,
        "effect_unit": "percent",
        "baseline": 59.40,
        "baseline_label": "GPT-3.5-turbo Call correctness when the API is given",
        "catalog_size": 73,
        "catalog_size_unit": "APIs",
        "catalog_scope": "API-Bank runnable evaluation system",
        "arxiv": "2304.08244",
        "doi": "10.48550/arXiv.2304.08244",
        "section_or_figure": "Table 3, GPT-3.5-turbo Retrieve+Call vs Call",
        "snapshot": "apibank-2304.08244.ar5iv.html",
        "snapshot_pin": "38.52%",
        "evidence_tier": "E1",
        "confidence_band": "HIGH",
        "can_promote": True,
        "notes": "Second model at the same catalog size of 73.",
    },
    {
        "id": "F-TOOLKEN-GSM8K-XL",
        "mechanism": "learned",
        "partition": "B",
        "family": "toolken",
        "metric": "exact-match accuracy (GSM8K-XL)",
        "metric_kind": "end_to_end_task_accuracy",
        "effect_size": 0.33,
        "effect_unit": "fraction",
        "baseline": 0.32,
        "baseline_label": "ReAct exact-match on GSM8K-XL",
        "catalog_size": 4,
        "catalog_size_unit": "tools",
        "catalog_scope": "four arithmetic operators",
        "arxiv": "2305.11554",
        "doi": "10.48550/arXiv.2305.11554",
        "section_or_figure": "Table 2, ToolkenGPT vs ReAct on GSM8K-XL (4 tools)",
        "snapshot": "toolken-2305.11554.openreview-pdf.txt",
        "snapshot_pin": "ToolkenGPT (Ours) 0.33",
        "evidence_tier": "E1",
        "confidence_band": "HIGH",
        "can_promote": False,
        "notes": (
            "At catalog size 4, learned toolkens are within 1 point of ReAct. "
            "Accuracy at 4 tools says nothing about 500."
        ),
    },
    {
        "id": "F-TOOLKEN-FUNCQA",
        "mechanism": "learned",
        "partition": "B",
        "family": "toolken",
        "metric": "exact-match accuracy (FuncQA one-hop)",
        "metric_kind": "end_to_end_task_accuracy",
        "effect_size": 0.73,
        "effect_unit": "fraction",
        "baseline": 0.57,
        "baseline_label": "ReAct exact-match on FuncQA (13 tools)",
        "catalog_size": 13,
        "catalog_size_unit": "tools",
        "catalog_scope": "FuncQA calculator/tool set",
        "arxiv": "2305.11554",
        "doi": "10.48550/arXiv.2305.11554",
        "section_or_figure": "Table 2, ToolkenGPT vs ReAct on FuncQA (13 tools)",
        "snapshot": "toolken-2305.11554.openreview-pdf.txt",
        "snapshot_pin": "0.73",
        "evidence_tier": "E1",
        "confidence_band": "HIGH",
        "can_promote": True,
        "notes": "Learned toolkens beat in-context ReAct at catalog size 13.",
    },
    {
        "id": "F-TOOLKEN-VIRTUALHOME",
        "mechanism": "learned",
        "partition": "B",
        "family": "toolken",
        "metric": "Success (correct final state)",
        "metric_kind": "end_to_end_task_accuracy",
        "effect_size": 0.68,
        "effect_unit": "fraction",
        "baseline": 0.20,
        "baseline_label": "In-context learning Success on VirtualHome",
        "catalog_size": 58,
        "catalog_size_unit": "toolkens",
        "catalog_scope": "25 verbs + 32 objects + [END]",
        "arxiv": "2305.11554",
        "doi": "10.48550/arXiv.2305.11554",
        "section_or_figure": "Table 3, ToolkenGPT vs In-context Learning Success",
        "snapshot": "toolken-2305.11554.openreview-pdf.txt",
        "snapshot_pin": "ToolkenGPT (Ours) 1.00 0.82 0.68 0.70",
        "evidence_tier": "E1",
        "confidence_band": "HIGH",
        "can_promote": True,
        "notes": "Learned router at 58 tools; ICL Success is 0.20.",
    },
    {
        "id": "F-TOOLKEN-ICL-DROP-30",
        "mechanism": "native-in-context",
        "partition": "B",
        "family": "toolken",
        "metric": "KAMEL in-context tool selection (qualitative)",
        "metric_kind": "selection_accuracy_qualitative",
        "effect_size": None,
        "effect_unit": "none",
        "baseline": "~20% prompting accuracy across 30/60/100/234 tools",
        "baseline_label": "Prompting (parametric knowledge, no tools) ~20%",
        "catalog_size": 234,
        "catalog_size_unit": "tools",
        "catalog_scope": "KAMEL relations; subsets of 30, 60, 100, 234",
        "arxiv": "2305.11554",
        "doi": "10.48550/arXiv.2305.11554",
        "section_or_figure": "Section 4.2 and Figure 2",
        "snapshot": "toolken-2305.11554.openreview-pdf.txt",
        "snapshot_pin": "drastic performance drops when",
        "evidence_tier": "E3",
        "confidence_band": "MEDIUM",
        "can_promote": False,
        "notes": (
            "Exact per-size ICL percentages live in Figure 2 and were not "
            "extracted from the vector plot. The paper states ICL drops "
            "drastically above 30 tools because of context-length limits. "
            "Headline without a tabled effect size remains E3."
        ),
    },
    {
        "id": "F-ANYTOOL-TOOLBENCH-AVG",
        "mechanism": "retrieval-based",
        "partition": "B",
        "family": "anytool",
        "metric": "filtered ToolBench average pass rate (Eq 2)",
        "metric_kind": "end_to_end_pass_rate",
        "effect_size": 58.2,
        "effect_unit": "percent",
        "baseline": 22.9,
        "baseline_label": "ToolLLM retriever + ToolLLaMA DFSDT average pass rate",
        "catalog_size": 16000,
        "catalog_size_unit": "APIs",
        "catalog_scope": "RapidAPI pool used by AnyTool / ToolBench (>16,000 APIs)",
        "arxiv": "2402.04253",
        "doi": "10.48550/arXiv.2402.04253",
        "section_or_figure": "Table 1, AnyTool Avg. vs ToolLLM (ToolLLM's retriever) Avg.",
        "snapshot": "anytool-2402.04253.ar5iv.html",
        "snapshot_pin": "58.2",
        "evidence_tier": "E1",
        "confidence_band": "HIGH",
        "can_promote": False,
        "notes": (
            "Hierarchical GPT-4 retriever, not a learned dense retriever. Pass "
            "rate is not selection accuracy. GPT-4 DFSDT with reference APIs "
            "is 38.9 as a second baseline. Authors state 16k APIs exceed even "
            "a 128k context window, so native all-in-context is impossible here."
        ),
    },
    {
        "id": "F-ANYTOOL-CONTEXT-IMPOSSIBLE",
        "mechanism": "native-in-context",
        "partition": "B",
        "family": "anytool",
        "metric": "whether all API schemas fit in context",
        "metric_kind": "feasibility",
        "effect_size": 0,
        "effect_unit": "boolean-as-int (0=impossible)",
        "baseline": 1,
        "baseline_label": "native all-in-context assumed feasible",
        "catalog_size": 16000,
        "catalog_size_unit": "APIs",
        "catalog_scope": "RapidAPI pool used by AnyTool",
        "arxiv": "2402.04253",
        "doi": "10.48550/arXiv.2402.04253",
        "section_or_figure": "Section 5.2, Various GPT-4 Models paragraph",
        "snapshot": "anytool-2402.04253.ar5iv.html",
        "snapshot_pin": "exceeds the maximum context length of the model, even for the version with the largest context length of 128,000 tokens",
        "evidence_tier": "E1",
        "confidence_band": "HIGH",
        "can_promote": True,
        "notes": "Feasibility refute of native all-in-context at 16k APIs.",
    },
    {
        "id": "F-ANYTOOLBENCH-PR",
        "mechanism": "retrieval-based",
        "partition": "B",
        "family": "anytool",
        "metric": "AnyToolBench pass rate",
        "metric_kind": "end_to_end_pass_rate",
        "effect_size": 73.8,
        "effect_unit": "percent",
        "baseline": 18.9,
        "baseline_label": "ToolLLM retriever + ToolLLaMA pass rate on AnyToolBench",
        "catalog_size": 16000,
        "catalog_size_unit": "APIs",
        "catalog_scope": "full API pool, no reference APIs supplied",
        "arxiv": "2402.04253",
        "doi": "10.48550/arXiv.2402.04253",
        "section_or_figure": "Table 2, AnyTool vs ToolLLM",
        "snapshot": "anytool-2402.04253.ar5iv.html",
        "snapshot_pin": "73.8",
        "evidence_tier": "E1",
        "confidence_band": "HIGH",
        "can_promote": False,
        "notes": "GPT-4 plain-agent retriever scores 14.0 on the same table.",
    },
    {
        "id": "F-HUGGINGGPT-PLAN-NOT-SELECT",
        "mechanism": "rule-based",
        "partition": "B",
        "family": "hugginggpt",
        "metric": "single-task planning accuracy (GPT-3.5)",
        "metric_kind": "planning_accuracy_not_selection",
        "effect_size": 52.62,
        "effect_unit": "percent",
        "baseline": 23.86,
        "baseline_label": "Vicuna-7b single-task planning Acc",
        "catalog_size": 24,
        "catalog_size_unit": "task types",
        "catalog_scope": (
            "HuggingGPT Table 13 task list (24 task types, excluding category headers)"
        ),
        "arxiv": "2303.17580",
        "doi": "10.48550/arXiv.2303.17580",
        "section_or_figure": "Table 3 (planning Acc) and §3.2 / Table 13 (router mechanism)",
        "snapshot": "hugginggpt-2303.17580.ar5iv.html",
        "snapshot_pin": "52.62",
        "evidence_tier": "E3",
        "confidence_band": "LOW",
        "can_promote": False,
        "notes": (
            "Rule-based model selection is: filter by task type, rank by Hugging "
            "Face downloads, keep top-K, then in-context pick. The paper does not "
            "report model-selection accuracy against a gold model. Table 3 is "
            "task-type planning over 24 types, not tool selection from the Hub. "
            "Cannot promote a rule-based router from this number."
        ),
    },
    {
        "id": "F-NATIVE-PD-UNMEASURED",
        "mechanism": "native-progressive-disclosure",
        "partition": "B",
        "family": "native-pd",
        "metric": "skill-selection accuracy under native PD",
        "metric_kind": "selection_accuracy",
        "effect_size": None,
        "effect_unit": "none",
        "baseline": "not reported",
        "baseline_label": "no published native-PD vs retriever head-to-head",
        "catalog_size": 0,
        "catalog_size_unit": "published skill catalogs with a gold routing set",
        "catalog_scope": "Anthropic Agent Skills progressive disclosure (name+description always loaded)",
        "arxiv": None,
        "doi": None,
        "url": "https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview.md",
        "section_or_figure": "How Skills work / Level 1: Metadata (always loaded)",
        "snapshot": "claude-skills-overview.md",
        "snapshot_pin": "progressive disclosure",
        "evidence_tier": "E3",
        "confidence_band": "LOW",
        "can_promote": False,
        "notes": (
            "Native PD is a context-loading mechanism, not a measured router. "
            "The vendor docs do not publish selection accuracy at any catalog size."
        ),
    },
]


def figures_for(partition: str) -> list[dict]:
    return [f for f in FIGURES if f["partition"] == partition]


def promoted(figs: list[dict] | None = None) -> list[dict]:
    rows = FIGURES if figs is None else figs
    return [f for f in rows if f.get("can_promote") is True]
