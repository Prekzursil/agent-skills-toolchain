#!/usr/bin/env python3
"""Emit command-center/research/RES-0100.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import check as C  # noqa: E402
import evidence as E  # noqa: E402

OUT = "command-center/research/RES-0100.json"
SNAP = HERE / "snapshots"


def sha_name(name: str) -> str:
    return C.digest_file(SNAP / name)


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    used = sorted({f["snapshot"] for f in E.FIGURES})
    snap_sha = {name: sha_name(name) for name in used}

    def lineage(fig: dict) -> dict:
        return {
            "arxiv": fig.get("arxiv"),
            "doi": fig.get("doi"),
            "url": fig.get("url"),
            "section_or_figure": fig["section_or_figure"],
            "snapshot": fig["snapshot"],
            "snapshot_sha256": snap_sha[fig["snapshot"]],
            "snapshot_pin": fig["snapshot_pin"],
            "fetched_at": now,
        }

    figures = []
    for fig in E.FIGURES:
        row = dict(fig)
        row["source_lineage"] = lineage(fig)
        row["freshness_stamp"] = now
        figures.append(row)

    claims = [
        {
            "claim_id": "RES-0100-C-RETRIEVAL",
            "canonical_mechanism": (
                "Dense or hierarchical retrieval over tool/API documents, then "
                "an LLM caller on the shortlist."
            ),
            "source_lineage": [
                lineage(f)
                for f in E.FIGURES
                if f["family"] in {"gorilla", "toollm", "apibank", "anytool"}
                and f["mechanism"] == "retrieval-based"
            ][:4],
            "evidence_tier": "E1",
            "confidence_band": "HIGH",
            "settling_probe": (
                "Re-read Table 1 of Gorilla and Table 3 of ToolLLM from the "
                "snapshotted HTML; NDCG/AST numbers must match this record."
            ),
            "support_edges": ["RES-0100-C-CONTEXT-LIMIT"],
            "contradiction_edges": ["RES-0100-C-ADOPT-NATIVE"],
            "freshness_stamp": now,
            "snapshot_sha256": snap_sha["gorilla-2305.15334.ar5iv.html"],
            "summary": (
                "At catalog size 95 (Torch Hub) Gorilla+GPT-Index AST overall is "
                "61.82 vs GPT-4 0-shot 38.70. At 16,464 APIs a Sentence-BERT "
                "retriever reaches I1 NDCG@1 84.2 vs BM25 18.4 vs Ada-002 57.5. "
                "At 73 APIs GPT-4 Retrieve+Call is 37.04 vs Call 63.66. Retrieval "
                "is measured; it is not free: BM25 can hurt Gorilla vs 0-shot."
            ),
        },
        {
            "claim_id": "RES-0100-C-LEARNED",
            "canonical_mechanism": (
                "Learned tool tokens / finetuned selectors (ToolkenGPT, Gorilla)."
            ),
            "source_lineage": [
                lineage(f)
                for f in E.FIGURES
                if f["family"] in {"toolken", "gorilla"} and f["mechanism"] == "learned"
            ],
            "evidence_tier": "E1",
            "confidence_band": "HIGH",
            "settling_probe": (
                "Re-read ToolkenGPT Table 2 (catalog 4 and 13) and Table 3 "
                "(catalog 58) from the snapshotted PDF extract."
            ),
            "support_edges": ["RES-0100-C-CONTEXT-LIMIT"],
            "contradiction_edges": ["RES-0100-C-ADOPT-NATIVE"],
            "freshness_stamp": now,
            "snapshot_sha256": snap_sha["toolken-2305.11554.openreview-pdf.txt"],
            "summary": (
                "At 4 tools ToolkenGPT 0.33 vs ReAct 0.32 (no material gap). At "
                "13 tools 0.73 vs ReAct 0.57. At 58 toolkens Success 0.68 vs ICL "
                "0.20. Learned routers help as N grows; numbers at 4 do not "
                "transfer to 500."
            ),
        },
        {
            "claim_id": "RES-0100-C-RULE",
            "canonical_mechanism": (
                "Rule-based selection: task-type filter, popularity rank, top-K, "
                "then in-context pick (HuggingGPT §3.2)."
            ),
            "source_lineage": [
                lineage(f) for f in E.FIGURES if f["family"] == "hugginggpt"
            ],
            "evidence_tier": "E3",
            "confidence_band": "LOW",
            "settling_probe": (
                "Confirm HuggingGPT §3.2 describes the download-rank rule and "
                "that Table 3 reports planning Acc, not model-selection Acc."
            ),
            "support_edges": [],
            "contradiction_edges": [],
            "freshness_stamp": now,
            "snapshot_sha256": snap_sha["hugginggpt-2303.17580.ar5iv.html"],
            "summary": (
                "HuggingGPT GPT-3.5 single-task planning Acc is 52.62 vs Vicuna "
                "23.86 at 24 task types. Model-selection accuracy of the "
                "download-rank rule is not reported, so the rule-based router "
                "cannot be promoted."
            ),
        },
        {
            "claim_id": "RES-0100-C-CONTEXT-LIMIT",
            "canonical_mechanism": (
                "Putting every tool description in context (the native-in-context "
                "regime that progressive disclosure still uses at Level 1)."
            ),
            "source_lineage": [
                lineage(f)
                for f in E.FIGURES
                if f["id"]
                in {"F-TOOLKEN-ICL-DROP-30", "F-ANYTOOL-CONTEXT-IMPOSSIBLE"}
            ],
            "evidence_tier": "E1",
            "confidence_band": "HIGH",
            "settling_probe": (
                "Re-read AnyTool §5.2 128k-context sentence and ToolkenGPT §4.2 "
                "ICL drop-above-30 sentence from snapshots."
            ),
            "support_edges": ["RES-0100-C-RETRIEVAL", "RES-0100-C-LEARNED"],
            "contradiction_edges": ["RES-0100-C-ADOPT-NATIVE"],
            "freshness_stamp": now,
            "snapshot_sha256": snap_sha["anytool-2402.04253.ar5iv.html"],
            "summary": (
                "ToolkenGPT: in-context learning drops drastically above 30 tools. "
                "AnyTool: 16,000 API schemas exceed a 128k context window. Native "
                "all-in-context is size-limited."
            ),
        },
        {
            "claim_id": "RES-0100-C-ADOPT-NATIVE",
            "canonical_mechanism": (
                "Inherited 05-ECO grade: adopt native progressive disclosure; "
                "do not build a bespoke retriever."
            ),
            "source_lineage": [
                {
                    "path": "command-center/WORK-UNIT-CATALOG.json",
                    "section_or_figure": "RES-0100 inputs (05-ECO :83-84,100)",
                    "note": (
                        "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md is not on this "
                        "Linux worktree; the inherited grade is taken from the "
                        "catalog citation only."
                    ),
                    "snapshot_sha256": None,
                },
                lineage(next(f for f in E.FIGURES if f["id"] == "F-NATIVE-PD-UNMEASURED")),
            ],
            "evidence_tier": "E3",
            "confidence_band": "LOW",
            "settling_probe": E.SETTLING_COMPARISON,
            "support_edges": [],
            "contradiction_edges": [
                "RES-0100-C-RETRIEVAL",
                "RES-0100-C-LEARNED",
                "RES-0100-C-CONTEXT-LIMIT",
            ],
            "freshness_stamp": now,
            "snapshot_sha256": snap_sha["claude-skills-overview.md"],
            "summary": (
                "Vendor docs describe native PD as always loading name+description. "
                "They publish no selection accuracy. Published measurements refute "
                "the unconditional 'never build a retriever' reading."
            ),
        },
    ]

    adopt = {
        "target": E.INHERITED_GRADE,
        "verdict": "REFUTED",
        "corroborate_or_refute": "REFUTE",
        "what_is_refuted": (
            "The inherited grade as an unconditional, size-independent instruction "
            "to adopt native progressive disclosure and reject a bespoke retriever."
        ),
        "what_survives": (
            "Native PD remains a reasonable default at small catalogs (ToolkenGPT "
            "shows in-context still works near 13-30 tools; API-Bank Call at 73 "
            "is 63.66% when the API is given). It is unmeasured on this estate."
        ),
        "deciding_evidence": (
            "AnyTool §5.2: 16k API schemas do not fit in a 128k window, so native "
            "all-in-context is impossible at that size. ToolkenGPT §4.2: ICL "
            "collapses above 30 tools. ToolLLM Table 3: a trained retriever is "
            "required to rank 16,464 APIs (NDCG@1 84.2 vs BM25 18.4). No paper "
            "reports native-PD selection accuracy at any catalog size, so the "
            "inherited grade cannot be promoted from published measurements."
        ),
        "deciding_figure_ids": [
            "F-ANYTOOL-CONTEXT-IMPOSSIBLE",
            "F-TOOLKEN-ICL-DROP-30",
            "F-TOOLLLM-NDCG-I1",
            "F-NATIVE-PD-UNMEASURED",
        ],
        "settling_comparison": E.SETTLING_COMPARISON,
        "strongest_caveat": (
            "This estate's live skill/tool count is not measured here (that is "
            "RES-0101). If the live catalog is <<30, native PD may still win on "
            "cost; the published record only refutes treating adopt-native as "
            "settled for large catalogs."
        ),
    }

    doc = {
        "unit_id": "RES-0100",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0100",
        "completion_sentinel": (
            "SUCCESS:RES-0100 in the receipt AND a corroborate-or-refute verdict "
            "with every accuracy figure annotated by its catalog size"
        ),
        "schema": "command-center/schema/research-claim-record.schema.json",
        "schema_status": (
            "PROVISIONAL-inline: RES-0001 schema file is absent on this tree; "
            "fields follow the RES-0001 question_or_target (claim id, canonical "
            "mechanism, source lineage, evidence tier E1-E4, confidence band, "
            "named settling probe, contradiction/support edges, freshness stamp, "
            "snapshot sha256)."
        ),
        "title": (
            "Compare retrieval, rule-based and learned capability routing on "
            "measured selection accuracy"
        ),
        "question": E.QUESTION,
        "inherited_grade": E.INHERITED_GRADE,
        "adopt_native_verdict": adopt,
        "accuracy_figures": figures,
        "claims": claims,
        "mechanisms": [
            {
                "id": "retrieval-based",
                "promoted": True,
                "why": (
                    "E1 figures with effect and baseline at catalog sizes 73, 95, "
                    "925, and 16464."
                ),
            },
            {
                "id": "learned",
                "promoted": True,
                "why": (
                    "E1 figures at catalog sizes 13 and 58; size-4 result cannot "
                    "promote by itself."
                ),
            },
            {
                "id": "rule-based",
                "promoted": False,
                "why": "HuggingGPT did not report selection accuracy; E3 only.",
            },
            {
                "id": "native-progressive-disclosure",
                "promoted": False,
                "why": "No published accuracy at any catalog size.",
            },
        ],
        "reviewers": [
            {
                "id": "RES-0100-reviewer-A-retrieval-partition",
                "role": "independent-partition-A",
                "source_partition": list(E.PART_A),
                "families": list(E.PART_A),
                "probe": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0100/probe1_catalog_size.py"
                ),
                "assignment": (
                    "Gorilla, ToolLLM, API-Bank only. Confirm every accuracy "
                    "figure has catalog_size and baseline."
                ),
            },
            {
                "id": "RES-0100-reviewer-B-learned-native-partition",
                "role": "independent-partition-B",
                "source_partition": list(E.PART_B),
                "families": list(E.PART_B),
                "probe": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0100/probe2_adopt_native.py"
                ),
                "assignment": (
                    "ToolkenGPT, AnyTool, HuggingGPT, Anthropic native PD. "
                    "Issue the corroborate-or-refute on adopt-native. Same-vendor "
                    "second reviewer on the same input is forbidden (05-ECO "
                    "anti-adoption #2); partitions are disjoint."
                ),
            },
        ],
        "tests": [
            {
                "id": "adopt-native-verdict",
                "requirement": (
                    "state corroborate or refute on the adopt-native grade with "
                    "the evidence that decides it"
                ),
                "result": "REFUTE",
            },
            {
                "id": "catalog-size-control",
                "requirement": (
                    "report the catalog size each published accuracy figure was "
                    "measured at, since accuracy at 20 tools says nothing about 500"
                ),
                "distinct_catalog_sizes": sorted(
                    {int(f["catalog_size"]) for f in E.FIGURES}
                ),
                "result": "PASS",
            },
        ],
        "snapshot_sha256": snap_sha,
        "freshness_stamp": now,
        "output_path": OUT,
        "dependencies_note": (
            "RES-0001 schema file and RES-0003 grader are leftover on this "
            "tree; this record is self-typed against the catalog field list."
        ),
    }

    ok, why = C.check_record(doc, REPO)
    if not ok:
        print("FAILED:RES-0100 emit checker red")
        for line in why:
            print(" ", line)
        return 1
    mutant = C.mutant_strip_catalog_size(doc)
    mok, mwhy = C.check_record(mutant, REPO)
    if mok:
        print("FAILED:RES-0100 emit mutant with catalog_size stripped was green")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT}")
    print(f"mutant_without_catalog_size_reasons={mwhy[:2]}")
    print("SUCCESS:RES-0100 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
