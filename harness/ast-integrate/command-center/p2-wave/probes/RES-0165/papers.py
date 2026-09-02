#!/usr/bin/env python3
"""Published-paper extractors. Numbers come from captured snapshot bytes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SNAP = HERE / "snapshots"

# Substrings that must occur in the named snapshot or the extract is refused.
MONKEYS_SWE_1 = "15.9% with one sample"
MONKEYS_SWE_250 = "56% with 250 samples"
MONKEYS_PLATEAU = "plateau beyond several hundred samples"
SNELL_4X = "more than 4x compared to a best-of-N baseline"
SNELL_14X = "outperform a 14x larger model"
AGENTS_SCALE = "scales with the number of agents instantiated"
AGENTS_DIFFICULTY = "degree of enhancement is correlated to the task difficulty"
DEBATE_MULTI = "multiple language model instances propose and debate"


def load_index() -> dict[str, Any]:
    path = SNAP / "index.json"
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot_text(rel_name: str) -> str:
    return (SNAP / rel_name).read_text(encoding="utf-8", errors="replace")


def rail_row(index: dict, eid: str) -> dict[str, Any] | None:
    for rec in index.get("rails") or []:
        if rec.get("id") == eid:
            return rec
    return None


def require_200(rec: dict[str, Any] | None, eid: str) -> dict[str, Any]:
    if rec is None:
        raise RuntimeError(f"missing rail {eid}")
    if int(rec.get("http_status") or 0) != 200:
        raise RuntimeError(f"rail {eid} http {rec.get('http_status')}")
    if len(str(rec.get("sha256") or "")) != 64:
        raise RuntimeError(f"rail {eid} missing sha256")
    return rec


def extract() -> dict[str, Any]:
    index = load_index()
    monkeys_atom = require_200(rail_row(index, "llm-monkeys-structured-api"), "llm-monkeys-structured-api")
    monkeys_abs = require_200(rail_row(index, "llm-monkeys-prose-source"), "llm-monkeys-prose-source")
    agents_atom = require_200(rail_row(index, "more-agents-structured-api"), "more-agents-structured-api")
    agents_abs = require_200(rail_row(index, "more-agents-prose-source"), "more-agents-prose-source")
    debate_atom = require_200(rail_row(index, "multiagent-debate-structured-api"), "multiagent-debate-structured-api")
    debate_abs = require_200(rail_row(index, "multiagent-debate-prose-source"), "multiagent-debate-prose-source")
    snell_atom = require_200(rail_row(index, "snell-test-time-structured-api"), "snell-test-time-structured-api")
    snell_abs = require_200(rail_row(index, "snell-test-time-prose-source"), "snell-test-time-prose-source")

    monkeys_text = snapshot_text("llm-monkeys-structured-api.body")
    snell_text = snapshot_text("snell-test-time-structured-api.body")
    agents_text = snapshot_text("more-agents-structured-api.body")
    debate_text = snapshot_text("multiagent-debate-structured-api.body")

    for blob, needle, label in (
        (monkeys_text, MONKEYS_SWE_1, "monkeys-1"),
        (monkeys_text, MONKEYS_SWE_250, "monkeys-250"),
        (monkeys_text, MONKEYS_PLATEAU, "monkeys-plateau"),
        (snell_text, SNELL_4X, "snell-4x"),
        (snell_text, SNELL_14X, "snell-14x"),
        (agents_text, AGENTS_SCALE, "agents-scale"),
        (agents_text, AGENTS_DIFFICULTY, "agents-difficulty"),
        (debate_text, DEBATE_MULTI, "debate-multi"),
    ):
        if needle not in blob:
            raise RuntimeError(f"extract {label} substring missing from captured bytes")

    coverage_1 = 15.9
    coverage_250 = 56.0
    n1, n250 = 1, 250
    extra = n250 - n1
    delta = coverage_250 - coverage_1
    later_mean = delta / float(extra)
    first_over_later = coverage_1 / later_mean

    return {
        "papers": {
            "llm-monkeys": {
                "arxiv": "2407.21787",
                "title": "Large Language Monkeys: Scaling Inference Compute with Repeated Sampling",
                "rails": [monkeys_atom, monkeys_abs],
                "extracted": {
                    "swe_lite_coverage_n1_percent": coverage_1,
                    "swe_lite_coverage_n250_percent": coverage_250,
                    "majority_vote_plateau": "several hundred samples",
                    "locator": "arXiv Atom <summary> of 2407.21787v3",
                },
                "compute_matched": {
                    "coverage_delta_pp": round(delta, 6),
                    "extra_samples": extra,
                    "mean_pp_per_extra_sample": round(later_mean, 6),
                    "first_sample_over_later_mean": round(first_over_later, 6),
                    "note": (
                        "Coverage still grows from n=1 to n=250, but per-sample "
                        "yield collapses vs the first sample. Majority voting "
                        "(the certainty aggregator) plateaus beyond several "
                        "hundred samples. That is the published analogue of "
                        "landscape/coverage vs targeted/vote flatten."
                    ),
                },
            },
            "more-agents": {
                "arxiv": "2402.05120",
                "title": "More Agents Is All You Need",
                "rails": [agents_atom, agents_abs],
                "extracted": {
                    "method": "sampling-and-voting (Agent Forest)",
                    "scales_with_n_agents": True,
                    "enhancement_correlated_to_task_difficulty": True,
                    "numeric_flatten_n_in_abstract": False,
                    "locator": "arXiv Atom <summary> of 2402.05120v2",
                },
                "compute_matched": {
                    "note": (
                        "Abs-level bytes do not contain a flatten N. The "
                        "promoted claim is qualitative: voting ensembles scale "
                        "with N and the gain tracks task difficulty. Table "
                        "points were not in the abs HTML capture."
                    ),
                },
            },
            "multiagent-debate": {
                "arxiv": "2305.14325",
                "title": "Improving Factuality and Reasoning in Language Models through Multiagent Debate",
                "rails": [debate_atom, debate_abs],
                "extracted": {
                    "method": "multiple instances propose and debate over multiple rounds",
                    "numeric_flatten_n_in_abstract": False,
                    "locator": "arXiv Atom <summary> of 2305.14325v1",
                },
                "compute_matched": {
                    "note": (
                        "Abs-level bytes name the debate procedure, not a "
                        "marginal-yield table. N is not compute-matched here."
                    ),
                },
            },
            "snell-test-time": {
                "arxiv": "2408.03314",
                "title": "Scaling LLM Test-Time Compute Optimally can be More Effective than Scaling Model Parameters",
                "rails": [snell_atom, snell_abs],
                "extracted": {
                    "compute_optimal_vs_best_of_n": "more than 4x",
                    "flops_matched_vs_larger_model": "14x",
                    "locator": "arXiv Atom <summary> of 2408.03314v1",
                },
                "compute_matched": {
                    "note": (
                        "Best-of-N is the naive extra-sample baseline. A "
                        "compute-optimal allocator beats it by >4x, which is "
                        "published evidence that unguided extra parallel "
                        "attempts waste budget after early yield."
                    ),
                },
            },
        },
        "s2_partial": {
            "more-agents": rail_row(index, "more-agents-structured-api-s2"),
            "multiagent-debate": rail_row(index, "multiagent-debate-structured-api-s2"),
            "llm-monkeys_http": (rail_row(index, "llm-monkeys-structured-api-s2") or {}).get("http_status"),
            "snell_http": (rail_row(index, "snell-test-time-structured-api-s2") or {}).get("http_status"),
            "note": "Semantic Scholar 429s are recorded; arXiv Atom is the structured rail used for promotion.",
        },
    }
