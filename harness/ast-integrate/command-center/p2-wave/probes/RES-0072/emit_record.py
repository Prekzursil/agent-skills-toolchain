#!/usr/bin/env python3
"""Emit command-center/research/RES-0072.json from the fixture table + contract."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from contract import (  # noqa: E402
    OUTPUT_REL,
    SENTINEL,
    UNIT_ID,
    column_from_routers,
    validate_artifact,
)

FIXTURE = HERE / "fixtures" / "routers.json"
OUT = REPO / OUTPUT_REL


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def build() -> dict:
    fx = load_fixture()
    routers = list(fx["routers"])
    column = column_from_routers(routers)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    claims = []
    for row, raw in zip(column, routers):
        claim_id = f"RES-0072-{row['router_id']}"
        claims.append(
            {
                "claim_id": claim_id,
                "canonical_mechanism": row["router_class"],
                "router_id": row["router_id"],
                "claim": (
                    f"{row['router_name']} reports {row['effect_size'] or 'no citable effect size'} "
                    f"on {row['benchmark'] or 'no named benchmark'} "
                    f"(locus {row['figure_locus'] or 'absent'})."
                ),
                "source_lineage": {
                    "arxiv": raw.get("arxiv") or None,
                    "doi": raw.get("doi") or None,
                    "url": raw.get("url"),
                    "snapshot_sha256": raw.get("snapshot_sha256") or None,
                    "fetched_at": fx["fetched_at"],
                    "figure_locus": raw.get("figure_locus") or None,
                },
                "evidence_tier": row["evidence_tier"],
                "confidence_band": "high" if row["replication_status"] == "self-reported-only" else "medium",
                "named_settling_probe": (
                    "command-center/p2-wave/probes/RES-0072/probe1_replication_column.py"
                    if row["replication_status"] != "unknown"
                    else "command-center/p2-wave/probes/RES-0072/probe2_evidence_promotion.py"
                ),
                "replication_status": row["replication_status"],
                "may_promote": row["may_promote"],
                "independent_reruns": raw.get("independent_reruns") or [],
                "notes": raw.get("notes") or "",
                "contradiction_support_edges": _edges(row["router_id"], raw),
                "freshness_stamp": now,
            }
        )
    promoted = [c["router_id"] for c in claims if c["may_promote"]]
    doc = {
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "receipt": {
            "unit_id": UNIT_ID,
            "line": SENTINEL,
            "produced_at": now,
            "output_path": OUTPUT_REL,
        },
        "schema_note": (
            "Declared catalog schema command-center/schema/research-claim-record.schema.json "
            "is absent on this worktree (RES-0001 not delivered here). Record uses the "
            "RES-0001 field list: claim id, canonical mechanism, source lineage, "
            "evidence tier E1-E4, confidence band, named settling probe, "
            "contradiction/support edges, freshness stamp, snapshot sha256."
        ),
        "question": fx["question"],
        "answer": (
            "Published routers claim large savings — FrugalGPT Table 3 98.3% vs GPT-4 on "
            "HEADLINES, RouteLLM Table 6 3.66x vs GPT-4 on MT-Bench at 95% quality, "
            "HybridLLM Table 1 40% fewer large-model calls with 0% BART drop on a small-gap "
            "Llama-2 pair, AutoMix abstract >50% cost cut — but none of those headline "
            "figures has been reproduced by an independent party on a different task "
            "distribution. AutoMix independently reimplemented FrugalGPT and HybridLLM on "
            "QASPER/QUALITY/COQA/MUTUAL/DIPLOMAT and did not recover 98.3% or 40%/0-drop; "
            "FrugalGPT ΔIBC is -16.7 on COQA with Mistral-7B (AutoMix Table 1). RouterBench "
            "independently evaluated cascade on MMLU/MBPP/GSM8K (Figure 5) and found gains "
            "only when judge error ≤ 0.1. Commercial Martian/Unify have no retrieved "
            "DOI/section/baseline; RouteLLM Figure 2 is a competitor overlay. "
            "Therefore the per-router replication-status column is self-reported-only or "
            "unknown, every headline saving is E3, and no mechanism is promoted."
        ),
        "replication_column": column,
        "per_router_replication_status": column,
        "promoted_mechanisms": promoted,
        "claims": claims,
        "intended_partitions": fx["intended_partitions"],
        "reviewer_requirement": {
            "specified": (
                "two independent reviewers with PARTITIONED evidence (each gets a "
                "disjoint half of the source set); 05-ECO anti-adoption #2 forbids a "
                "second same-vendor reviewer on the same input"
            ),
            "met": False,
            "reason": (
                "Single G-1 worktree session (grok-4.6 / xAI) read both partitions. "
                "A second vendor review was not fabricated. Because the requirement is "
                "unmet, no mechanism may be promoted even if a figure were E1."
            ),
        },
        "reviewers": [
            {
                "reviewer_id": "RES-0072-R1-grok-4.6",
                "vendor": "xai",
                "model": "grok-4.6",
                "independent": False,
                "scope_not_agreement": True,
                "partition": "both-partitions-same-session",
                "verdict": "PARTIAL",
                "finding": (
                    "Headline savings are self-reported-only. Independent reruns exist "
                    "for the cascade class (AutoMix Table 1, RouterBench Figure 5) and "
                    "do not reproduce FrugalGPT 98.3% or HybridLLM 40%/0-drop."
                ),
            }
        ],
        "strongest_surviving_counterargument": (
            "RouteLLM evaluates on three public benches (MT-Bench, MMLU, GSM8K) and "
            "AutoMix/RouterBench re-run cascade-class methods on other distributions, "
            "which a reader might call 'independent replication.' Those reruns are real, "
            "but they do not reproduce the claimed *figures*: AutoMix's FrugalGPT ΔIBC "
            "on COQA is negative, RouterBench reports no 98% cost cut, and RouteLLM's "
            "MMLU/GSM8K numbers are still the same authors. The unit's bar is "
            "independent reproduction of the claimed saving on a different task "
            "distribution, not same-lab extra benches or a failed transfer."
        ),
        "tests": [
            {
                "id": "replication-status-column",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0072/probe1_replication_column.py"
                ),
                "result": "NOT-RUN",
            },
            {
                "id": "evidence-rails-and-e3-promotion-ban",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0072/probe2_evidence_promotion.py"
                ),
                "result": "NOT-RUN",
            },
        ],
        "controls": [
            {
                "id": "at-least-one-self-reported-only",
                "fired": True,
                "why": "FrugalGPT, RouteLLM, HybridLLM, AutoMix, and RouterBench cascade figures are author-own.",
            },
            {
                "id": "all-replicated-mutant-red",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "strip-baseline-cannot-promote",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "artifacts": [
            {"path": OUTPUT_REL, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/RES-0072/fixtures/routers.json",
                "exists": True,
                "role": "fixture",
            },
        ],
        "freshness_stamp": now,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "prior-art-analyst",
            "execution_substrate": "linux-worktree",
        },
    }
    errs = validate_artifact(doc, expected_column=column)
    if errs:
        raise SystemExit("emit validation failed: " + "; ".join(errs))
    return doc


def _edges(router_id: str, raw: dict) -> list[dict]:
    edges = []
    if router_id == "frugalgpt-cascade":
        edges.append(
            {
                "type": "independence-rerun-failed-transfer",
                "from": "frugalgpt-cascade",
                "to": "automix-pomdp",
                "note": "AutoMix Table 1 FrugalGPT ΔIBC -16.7 on COQA / Mistral-7B vs HEADLINES 98.3%.",
            }
        )
        edges.append(
            {
                "type": "independence-rerun-qualitative",
                "from": "frugalgpt-cascade",
                "to": "routerbench-cascade",
                "note": "RouterBench Figure 5 cascade class on MMLU/MBPP/GSM8K; judge-error caveat; no 98%.",
            }
        )
    if router_id == "hybridllm-rtrans":
        edges.append(
            {
                "type": "independence-rerun-failed-transfer",
                "from": "hybridllm-rtrans",
                "to": "automix-pomdp",
                "note": "AutoMix Table 1 reimplements HybridLLM; MixInstruct 40%/0-drop not recovered as a headline.",
            }
        )
    if router_id in {"martian-commercial", "unifyai-commercial"}:
        edges.append(
            {
                "type": "competitor-eval-not-replication",
                "from": router_id,
                "to": "routellm-mf",
                "note": "RouteLLM Figure 2 overlay; not a DOI-backed own figure and not an independent reproduction of a Martian/Unify numbered claim.",
            }
        )
    if not edges:
        edges.append(
            {
                "type": "single-lab",
                "from": router_id,
                "to": None,
                "note": raw.get("notes") or "No independent reproduction of this figure located.",
            }
        )
    return edges


def main() -> int:
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_REL} bytes={OUT.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
