#!/usr/bin/env python3
"""Applicability + evidence-tier engine for the RES-0093 benchmark register.

A headline number without a baseline is E3 and cannot promote a mechanism.
A row is applicable only when (1) the environment kind can move when THIS
program's harness changes with weights held fixed, (2) at least one E1/E2
citation exists, and (3) a named harness-level improvement is attached.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
FACTS = HERE / "fixtures" / "paper_facts.json"

# Environment kinds whose score can move if this harness (plugins/hooks/MCP/
# confirmation/test-runner) changes while model weights stay fixed.
APPLICABLE_KINDS = frozenset(
    {
        "repo_issue_repair",
        "tool_api_policy",
        "plugin_tool_assistant",
        "shell_os_agent",
    }
)
INAPPLICABLE_KIND_REASON = {
    "static_function_completion": (
        "Score is docstring-to-function pass@k on a frozen prompt set; a "
        "plugin/hook/MCP/confirmation change with weights held fixed does not "
        "move it."
    ),
    "static_knowledge_qa": (
        "Score is multiple-choice knowledge accuracy; it measures pretraining "
        "contents, not this program's harness."
    ),
    "gui_computer_use": (
        "Score is GUI/screenshot/pyautogui success on a real desktop; this "
        "program does not ship that action space."
    ),
    "web_gui_nav": (
        "Score is end-to-end web GUI navigation success; this program's "
        "surface is plugin/hook/MCP/confirmation, not a WebArena browser env."
    ),
    "public_saturated_repair": (
        "Public leaderboard is confounded by memorization and broken tests; "
        "score movement is not a clean harness-improvement detector."
    ),
}

IMPROVEMENTS = {
    "patch-apply-fail-to-pass-runner": {
        "kinds": frozenset({"repo_issue_repair"}),
        "text": (
            "Fail-closed patch apply plus FAIL_TO_PASS/PASS_TO_PASS test "
            "execution versus generate-only patch dump"
        ),
    },
    "plugin-actually-invoked": {
        "kinds": frozenset({"plugin_tool_assistant"}),
        "text": (
            "Plugin/MCP tools actually invoked versus listed-but-unloaded "
            "(GAIA Level-1 GPT-4 9.1% vs GPT-4+plugins 30.3%)"
        ),
    },
    "tool-policy-pass-hat-k": {
        "kinds": frozenset({"tool_api_policy"}),
        "text": (
            "Deterministic tool-result replay and policy checker that lifts "
            "pass^k, not only pass^1"
        ),
    },
    "shell-hook-executes": {
        "kinds": frozenset({"shell_os_agent"}),
        "text": (
            "Hook/shell adapter that executes OS commands instead of returning "
            "a listed-but-inert tool"
        ),
    },
}

PROMOTING_TIERS = frozenset({"E1", "E2"})


def load_facts(path: Path | None = None) -> dict:
    p = path or FACTS
    return json.loads(p.read_text(encoding="utf-8"))


def grade_claim(claim: dict) -> str:
    """E2 needs DOI/arXiv, section, effect size, AND baseline. Else E3/E4."""
    if claim.get("headline_without_baseline") is True:
        return "E3"
    effect = claim.get("effect_size")
    baseline = claim.get("baseline_value")
    section = str(claim.get("section") or "").strip()
    source = str(claim.get("arxiv") or claim.get("doi") or claim.get("permalink") or "").strip()
    if effect is None:
        return "E4"
    if baseline is None or not str(claim.get("baseline_label") or "").strip():
        return "E3"
    if not section or not source:
        return "E3"
    return "E2"


def citation_row(claim: dict) -> dict:
    tier = grade_claim(claim)
    out = {
        "claim_id": claim["id"],
        "arxiv": claim.get("arxiv"),
        "doi": claim.get("doi"),
        "permalink": claim.get("permalink"),
        "section": claim.get("section"),
        "metric": claim.get("metric"),
        "effect_size": claim.get("effect_size"),
        "effect_unit": claim.get("effect_unit"),
        "effect_label": claim.get("effect_label"),
        "baseline_value": claim.get("baseline_value"),
        "baseline_unit": claim.get("baseline_unit"),
        "baseline_label": claim.get("baseline_label"),
        "evidence_tier": tier,
        "headline_without_baseline": bool(claim.get("headline_without_baseline")),
    }
    return out


def named_improvement(bench: dict) -> str | None:
    iid = bench.get("improvement_id")
    if not iid:
        return None
    spec = IMPROVEMENTS.get(iid)
    if spec is None:
        return None
    if bench.get("environment_kind") not in spec["kinds"]:
        return None
    return spec["text"]


def decide_row(bench: dict) -> dict:
    kind = str(bench.get("environment_kind") or "")
    citations = [citation_row(c) for c in (bench.get("claims") or [])]
    promoting = [c for c in citations if c["evidence_tier"] in PROMOTING_TIERS]
    best_tier = "E4"
    if citations:
        order = {"E1": 0, "E2": 1, "E3": 2, "E4": 3}
        best_tier = sorted((c["evidence_tier"] for c in citations), key=lambda t: order[t])[0]
    improvement = named_improvement(bench)

    if kind not in APPLICABLE_KINDS:
        reason = INAPPLICABLE_KIND_REASON.get(
            kind,
            "Environment kind is not a harness-moveable agent eval for this program.",
        )
        return {
            "benchmark_id": bench["id"],
            "name": bench["name"],
            "popular": bool(bench.get("popular")),
            "environment_kind": kind,
            "measures": bench["measures"],
            "does_not_measure": bench["does_not_measure"],
            "contamination_status": bench["contamination_status"],
            "saturation_status": bench["saturation_status"],
            "applicability_verdict": "inapplicable",
            "applicability_reason": reason,
            "named_detectable_improvement": None,
            "evidence_tier": best_tier,
            "citations": citations,
            "strongest_caveat": bench["strongest_caveat"],
            "promoting_claim_ids": [],
        }

    if not promoting:
        return {
            "benchmark_id": bench["id"],
            "name": bench["name"],
            "popular": bool(bench.get("popular")),
            "environment_kind": kind,
            "measures": bench["measures"],
            "does_not_measure": bench["does_not_measure"],
            "contamination_status": bench["contamination_status"],
            "saturation_status": bench["saturation_status"],
            "applicability_verdict": "inapplicable",
            "applicability_reason": (
                "No E1/E2 citation with effect size AND baseline; E3 headline "
                "numbers cannot promote a mechanism."
            ),
            "named_detectable_improvement": None,
            "evidence_tier": best_tier,
            "citations": citations,
            "strongest_caveat": bench["strongest_caveat"],
            "promoting_claim_ids": [],
        }

    if not improvement:
        return {
            "benchmark_id": bench["id"],
            "name": bench["name"],
            "popular": bool(bench.get("popular")),
            "environment_kind": kind,
            "measures": bench["measures"],
            "does_not_measure": bench["does_not_measure"],
            "contamination_status": bench["contamination_status"],
            "saturation_status": bench["saturation_status"],
            "applicability_verdict": "inapplicable",
            "applicability_reason": (
                "A harness-moveable environment still cannot be marked "
                "applicable until the specific detectable improvement is named."
            ),
            "named_detectable_improvement": None,
            "evidence_tier": best_tier,
            "citations": citations,
            "strongest_caveat": bench["strongest_caveat"],
            "promoting_claim_ids": [c["claim_id"] for c in promoting],
        }

    return {
        "benchmark_id": bench["id"],
        "name": bench["name"],
        "popular": bool(bench.get("popular")),
        "environment_kind": kind,
        "measures": bench["measures"],
        "does_not_measure": bench["does_not_measure"],
        "contamination_status": bench["contamination_status"],
        "saturation_status": bench["saturation_status"],
        "applicability_verdict": "applicable",
        "applicability_reason": (
            "Holding model weights fixed, a change on this program's harness "
            f"surface would move {bench['name']} because {improvement}."
        ),
        "named_detectable_improvement": improvement,
        "evidence_tier": best_tier if best_tier in PROMOTING_TIERS else "E2",
        "citations": citations,
        "strongest_caveat": bench["strongest_caveat"],
        "promoting_claim_ids": [c["claim_id"] for c in promoting],
    }


def build_register(facts: dict | None = None) -> list[dict]:
    doc = facts if facts is not None else load_facts()
    rows = [decide_row(b) for b in doc["benchmarks"]]
    rows.sort(key=lambda r: r["benchmark_id"])
    return rows


def tests_from_register(rows: list[dict]) -> dict:
    applicable = [r for r in rows if r["applicability_verdict"] == "applicable"]
    named_ok = bool(applicable) and all(
        isinstance(r.get("named_detectable_improvement"), str)
        and len(r["named_detectable_improvement"]) >= 16
        for r in applicable
    )
    control = next(
        (
            r
            for r in rows
            if r["applicability_verdict"] == "inapplicable" and r.get("popular")
        ),
        None,
    )
    return {
        "named_improvement_per_applicable": named_ok,
        "applicable_count": len(applicable),
        "inapplicable_count": sum(
            1 for r in rows if r["applicability_verdict"] == "inapplicable"
        ),
        "inapplicable_popular_control": {
            "benchmark_id": (control or {}).get("benchmark_id"),
            "reason": (control or {}).get("applicability_reason"),
            "pass": control is not None,
        },
        "e3_cannot_promote": all(
            r["applicability_verdict"] != "applicable" or r["evidence_tier"] in PROMOTING_TIERS
            for r in rows
        ),
    }


def mutate_drop_baseline(facts: dict, claim_id: str) -> dict:
    doc = deepcopy(facts)
    for bench in doc["benchmarks"]:
        for claim in bench.get("claims") or []:
            if claim.get("id") == claim_id:
                claim["baseline_value"] = None
                claim["baseline_label"] = ""
                claim["headline_without_baseline"] = True
    return doc


def mutate_force_applicable(facts: dict, bench_id: str) -> dict:
    """Force a named improvement onto an inapplicable kind (must still fail)."""
    doc = deepcopy(facts)
    for bench in doc["benchmarks"]:
        if bench.get("id") == bench_id:
            bench["improvement_id"] = "patch-apply-fail-to-pass-runner"
            bench["environment_kind"] = bench.get("environment_kind")
    return doc


def mutate_strip_improvement(facts: dict, bench_id: str) -> dict:
    doc = deepcopy(facts)
    for bench in doc["benchmarks"]:
        if bench.get("id") == bench_id:
            bench["improvement_id"] = None
    return doc


def mutate_drop_inapplicable(facts: dict) -> dict:
    doc = deepcopy(facts)
    doc["benchmarks"] = [
        b
        for b in doc["benchmarks"]
        if b.get("environment_kind") in APPLICABLE_KINDS
    ]
    return doc


def mutate_drop_all_baselines(facts: dict, bench_id: str) -> dict:
    doc = deepcopy(facts)
    for bench in doc["benchmarks"]:
        if bench.get("id") == bench_id:
            for claim in bench.get("claims") or []:
                claim["baseline_value"] = None
                claim["baseline_label"] = ""
                claim["headline_without_baseline"] = True
    return doc
