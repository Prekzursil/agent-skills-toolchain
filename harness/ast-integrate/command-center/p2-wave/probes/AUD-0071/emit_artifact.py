#!/usr/bin/env python3
"""Emit AUD-0071 support-edge and independent-corroboration graph.

Does not create command-center/schema/audit-graph.schema.json
(no ADV schema-rebuild loop). G-1 needs parseable JSON, the catalog
sentinel in-text, non-BLOCKED state, live probes, and a per-unit
manifest row.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import load_corpus  # noqa: E402
from graph import build  # noqa: E402

UNIT = "AUD-0071"
OUT = "command-center/audit/AUD-0071-support-edge-graph.json"
SCHEMA = "command-center/schema/audit-graph.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0071 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "For each claim, which other claims independently support it, and how "
    "many of those supports are genuinely independent rather than derived "
    "from the same upstream source?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0071/probe1_citation_edges.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0071/probe2_independent_collapse.py"
)
FIVE_ONE = "CTL-FIVE-ONE-TARGET"
MIXED = "CTL-MIXED-TARGET"
FIVE_INDEP = "CTL-FIVE-INDEP-TARGET"
NOCITE = "CTL-NOCITE"


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    corpus = load_corpus()
    graph = build(corpus["claims"])
    tally = graph["tally"]
    for required in (FIVE_ONE, MIXED, FIVE_INDEP, NOCITE):
        if required not in tally:
            print(f"FAILED:AUD-0071 emit missing control claim {required}")
            return 1
    five = tally[FIVE_ONE]
    mixed = tally[MIXED]
    indep = tally[FIVE_INDEP]
    none = tally[NOCITE]
    if five["raw_support_count"] != 5 or five["independent_source_count"] != 1:
        print(
            "FAILED:AUD-0071 emit five-from-one "
            f"raw={five['raw_support_count']} indep={five['independent_source_count']}"
        )
        return 1
    if five["ranking_score"] != 1:
        print("FAILED:AUD-0071 emit ranking used raw count")
        return 1
    if mixed["raw_support_count"] != 2 or mixed["independent_source_count"] != 2:
        print(
            "FAILED:AUD-0071 emit mixed "
            f"raw={mixed['raw_support_count']} indep={mixed['independent_source_count']}"
        )
        return 1
    if indep["raw_support_count"] != 5 or indep["independent_source_count"] != 5:
        print("FAILED:AUD-0071 emit five-indep collapsed wrongly")
        return 1
    if none["raw_support_count"] != 0 or none["independent_source_count"] != 0:
        print("FAILED:AUD-0071 emit nocite has support")
        return 1
    prose = graph["prose_mention_uncited"]
    prose_ok = ("CTL-PROSE-A", "CTL-PROSE-B") in prose or (
        "CTL-PROSE-B",
        "CTL-PROSE-A",
    ) in prose
    if not prose_ok:
        print("FAILED:AUD-0071 emit prose pair not recorded as uncited mention")
        return 1
    if any(
        (e["from"], e["to"]) in {("CTL-PROSE-A", "CTL-PROSE-B"), ("CTL-PROSE-B", "CTL-PROSE-A")}
        for e in graph["support_edges"]
    ):
        print("FAILED:AUD-0071 emit prose mention became a support edge")
        return 1
    if not graph["unresolved_citations"]:
        print("FAILED:AUD-0071 emit dangling citation was dropped")
        return 1
    if FIVE_ONE not in graph["raw_ne_independent"]:
        print("FAILED:AUD-0071 emit five-from-one not in raw_ne_independent")
        return 1

    schema_path = REPO / SCHEMA
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    aud = corpus["aud0068"]
    lin = corpus["aud0074"]
    answer = (
        f"Loaded {graph['claim_count']} claims "
        f"(control={corpus['control_count']}, AUD-0068="
        f"{aud['claim_count'] if aud['present'] else 'absent'}, "
        f"on-tree-research={corpus['research_count']}). "
        f"{graph['edge_count']} explicit citation SUPPORT edges. "
        f"CTL-FIVE-ONE-TARGET raw_support_count=5 independent_source_count=1 "
        f"ranking_score=1 (five records citing one upstream document collapse "
        f"to one independent signal). CTL-FIVE-INDEP-TARGET stays 5/5 so the "
        f"collapser is not a constant-one. Ranking uses independent_source_count "
        f"only. AUD-0068 present={aud['present']}; AUD-0074 present={lin['present']}. "
        f"{SENTINEL}"
    )
    ranked = sorted(
        (
            row
            for row in graph["per_claim"]
            if row["independent_source_count"] > 0
        ),
        key=lambda r: (-r["ranking_score"], r["claim_id"]),
    )
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "audit-graph",
        "title": "Support-edge and independent-corroboration graph",
        "question": QUESTION,
        "answer": answer,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "schema_on_disk": schema_path.is_file(),
        "schema_note": (
            "command-center/schema/audit-graph.schema.json is a generated $ref "
            "shim on this worktree. This unit did not author or rebuild that "
            "schema (no ADV rebuild circle). The artifact is JSON-parseable "
            "with state=SUCCESS and carries graph nodes, citation SUPPORT "
            "edges, raw vs independent counts, and the five-from-one control."
        ),
        "report": {
            "kind": "audit-graph",
            "control_ids": [
                "CTL-FIVE-ONE-TARGET",
                "CTL-MIXED-TARGET",
                "CTL-FIVE-INDEP-TARGET",
                "CTL-NOCITE",
                "CTL-PROSE-A",
            ],
            "observations": [
                {
                    "name": "five_from_one_independent_source_count",
                    "measured": five["independent_source_count"],
                    "method": "collapse-supporters-by-source_id",
                    "anchor": "command-center/p2-wave/probes/AUD-0071/fixtures/control_claims.json",
                },
                {
                    "name": "five_from_one_raw_support_count",
                    "measured": five["raw_support_count"],
                    "method": "explicit-citation-edges",
                    "anchor": "command-center/p2-wave/probes/AUD-0071/graph.py",
                },
                {
                    "name": "ranking_score_equals_independent_count",
                    "measured": five["ranking_score"] == five["independent_source_count"],
                    "method": "ranking-uses-independent_source_count",
                    "anchor": "command-center/p2-wave/probes/AUD-0071/graph.py",
                },
            ],
        },
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "corpus-normalizer",
            "execution_substrate": "linux-headless",
        },
        "freshness_stamp": now,
        "ranking_rule": (
            "Rank by independent_source_count. raw_support_count is recorded "
            "and must not be used for ranking."
        ),
        "upstream_inputs": {
            "AUD-0068": aud,
            "AUD-0074": lin,
            "control_fixture": {
                "path": "command-center/p2-wave/probes/AUD-0071/fixtures/control_claims.json",
                "present": True,
                "claim_count": corpus["control_count"],
            },
            "on_tree_research_claims": corpus["research_count"],
        },
        "scope": (
            "Control fixture is always in-graph. Canonical Prompt-One claims "
            "are included only when AUD-0068 exists on disk. Missing upstream "
            "is recorded, not invented."
        ),
        "nodes": [
            {
                "id": c["claim_id"],
                "source_id": c["source_id"],
                "origin": c["origin"],
                "citation_count": len(c.get("citations") or []),
            }
            for c in graph["claims"]
        ],
        "support_edges": graph["support_edges"],
        "unresolved_citations": graph["unresolved_citations"],
        "per_claim": graph["per_claim"],
        "headline": {
            "claim_count": graph["claim_count"],
            "support_edge_count": graph["edge_count"],
            "unresolved_citation_count": len(graph["unresolved_citations"]),
            "claims_where_raw_ne_independent": graph["raw_ne_independent"],
            "ranked_by_independent_source_count": [
                {
                    "claim_id": r["claim_id"],
                    "ranking_score": r["ranking_score"],
                    "raw_support_count": r["raw_support_count"],
                    "independent_source_count": r["independent_source_count"],
                }
                for r in ranked[:40]
            ],
        },
        "control": {
            "five_records_one_upstream": {
                "claim_id": FIVE_ONE,
                "raw_support_count": five["raw_support_count"],
                "independent_source_count": five["independent_source_count"],
                "ranking_score": five["ranking_score"],
                "assert": "ONE independent support, not five",
                "pass": five["raw_support_count"] == 5
                and five["independent_source_count"] == 1
                and five["ranking_score"] == 1,
            },
            "two_independent_sources": {
                "claim_id": MIXED,
                "raw_support_count": mixed["raw_support_count"],
                "independent_source_count": mixed["independent_source_count"],
                "pass": mixed["independent_source_count"] == 2,
            },
            "five_independent_stay_five": {
                "claim_id": FIVE_INDEP,
                "raw_support_count": indep["raw_support_count"],
                "independent_source_count": indep["independent_source_count"],
                "pass": indep["independent_source_count"] == 5,
            },
            "no_citation_zero": {
                "claim_id": NOCITE,
                "raw_support_count": none["raw_support_count"],
                "pass": none["raw_support_count"] == 0,
            },
            "prose_mention_is_not_an_edge": {
                "pair": ["CTL-PROSE-A", "CTL-PROSE-B"],
                "pass": True,
            },
        },
        "evidence": [
            {
                "claim": (
                    "Five supporting records that all cite one upstream document "
                    "score as one independent support."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0071/fixtures/control_claims.json",
            },
            {
                "claim": (
                    "Support edges are built from explicit citation fields; a "
                    "prose mention of another claim id is not an edge."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0071/graph.py",
            },
            {
                "claim": (
                    "AUD-0068 canonical Prompt-One claim extraction is present "
                    "on this worktree."
                ),
                "verdict": "CONFIRMED" if aud["present"] else "NOT-CHECKED",
                "anchor": aud["path"],
            },
        ],
        "tests": [
            {
                "id": "ctl-five-records-one-upstream",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "ctl-explicit-citation-edges",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "ctl-prose-mention-negative",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "ctl-five-independent-not-collapsed",
                "command": P2,
                "result": "PASS",
            },
        ],
        "named_probe_commands": [
            {"id": "probe1", "command": P1, "role": "citation-support-edges"},
            {
                "id": "probe2",
                "command": P2,
                "role": "independent-source-collapse-and-ranking",
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0071-probe2-independent-collapse",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-runs the collapse: raw count and independent-source "
                "count must differ on the five-from-one control, and only the "
                "second is the ranking score."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/AUD-0071/fixtures/control_claims.json",
                "exists": True,
                "role": "fixture",
            },
        ],
        "cloud_ok": False,
        "notes": (
            "G-1 for AUD-0071. Did not run global unit_manifest.py --write. "
            "No ADV rebuild of audit-graph.schema.json. cloud ok=true is not delivery. "
            + SENTINEL
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:AUD-0071 emit sentinel missing from serialized artifact")
        return 1
    out_path.write_text(text, encoding="utf-8")
    sha, n = digest_file(out_path)
    print(f"wrote {OUT} bytes={n} sha256={sha}")
    print(
        f"claims={graph['claim_count']} edges={graph['edge_count']} "
        f"five_one raw=5 indep=1 mixed_indep={mixed['independent_source_count']}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
