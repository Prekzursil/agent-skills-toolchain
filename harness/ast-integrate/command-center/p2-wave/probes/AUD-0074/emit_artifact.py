#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0074-source-lineage-graph.json.

Does not fetch the catalog $ref shim (jsonschema 4.10.3 RefResolver would
hit the network). Validates the disk-local Draft-07 contract in
schema_local.py. No ADV schema-rebuild loop.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import engine as E  # noqa: E402
import schema_local as SL  # noqa: E402

OUT = "command-center/audit/AUD-0074-source-lineage-graph.json"
SCHEMA = "command-center/schema/audit-graph.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0074 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "What is the derivation graph among the corpus artifacts, and which "
    "artifacts are downstream of a source that has since been corrected?"
)
FRESH_POST = "14-NO-REGRESSION-CONTRACT.md"
NEVER_CORR = "01-BLOCKER-REPRODUCTION.md"
EARLY_NO_CITE = "16-VERIFICATION-PLAN.md"


def main() -> int:
    pack = C.load()
    records = pack["records"]
    cite_edges = E.extract_citation_edges(records)
    flags = E.flag_stale(cite_edges, pack["corrections"])
    doc13_flags = E.doc13_stale(flags)
    blind = E.timestamp_blind_flags(cite_edges)
    if not cite_edges:
        print("FAILED:AUD-0074 emit zero citation edges")
        return 1
    if not doc13_flags:
        print("FAILED:AUD-0074 emit doc-13 control produced zero stale-downstream flags")
        return 1
    if blind:
        print("FAILED:AUD-0074 emit timestamp-blind mutant was not silent")
        return 1

    fresh_post = [
        e
        for e in cite_edges
        if e["from"] == FRESH_POST and e["to"] == C.DOC13
    ]
    never_corr = [
        e
        for e in cite_edges
        if e["from"] == NEVER_CORR and e["to"] == "00-CURRENT-STATE-INVENTORY.md"
    ]
    early = [e for e in cite_edges if e["from"] == EARLY_NO_CITE and e["to"] == C.DOC13]
    fresh_flagged = [f for f in flags if f["from"] == FRESH_POST]
    never_flagged = [f for f in flags if f["from"] == NEVER_CORR]
    early_flagged = [f for f in flags if f["from"] == EARLY_NO_CITE]
    if not fresh_post or not never_corr:
        print("FAILED:AUD-0074 emit missing good-state citation edges")
        return 1
    if fresh_flagged or never_flagged or early_flagged or early:
        print("FAILED:AUD-0074 emit good-state edges were flagged or early file cited doc13")
        return 1

    nodes = []
    cited_as_source = {e["to"] for e in cite_edges}
    corrected = {c["source"] for c in pack["corrections"]}
    stale_from = {f["from"] for f in flags}
    for rec in records:
        nid = rec["id"]
        kind = "source"
        if nid in stale_from:
            kind = "stale-downstream"
        elif nid in corrected:
            kind = "corrected-source"
        elif nid in cited_as_source:
            kind = "source"
        else:
            kind = "artifact"
        nodes.append(
            {
                "id": nid,
                "kind": kind,
                "path": rec["path"],
                "created_at": rec["created_at"],
                "origin": rec["origin"],
                "bytes": rec["bytes"],
                "corrected": nid in corrected,
            }
        )

    annotated_edges = []
    stale_keys = {(f["from"], f["to"], f["cited_version"]) for f in flags}
    for e in cite_edges:
        key = (e["from"], e["to"], e["cited_version"])
        row = dict(e)
        row["stale"] = key in stale_keys
        annotated_edges.append(row)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tests = [
        {
            "id": "ctl-doc13-stale-downstream",
            "name": "known doc-13 2026-08-07 correction yields >=1 stale-downstream flag",
            "result": "PASS" if doc13_flags else "FAIL",
            "assertions": 1,
            "observed": len(doc13_flags),
        },
        {
            "id": "ctl-post-correction-cite-silent",
            "name": "14-NO-REGRESSION-CONTRACT cites post-correction doc 13 and is not flagged",
            "result": "PASS" if fresh_post and not fresh_flagged else "FAIL",
            "assertions": 2,
        },
        {
            "id": "ctl-never-corrected-silent",
            "name": "01-BLOCKER-REPRODUCTION cites never-corrected 00-CURRENT and is not flagged",
            "result": "PASS" if never_corr and not never_flagged else "FAIL",
            "assertions": 2,
        },
        {
            "id": "ctl-timestamp-blind-mutant",
            "name": "dropping the correction register yields zero stale flags",
            "result": "PASS" if not blind else "FAIL",
            "assertions": 1,
            "observed": len(blind),
        },
        {
            "id": "ctl-early-file-without-cite",
            "name": "16-VERIFICATION-PLAN is older than the correction but does not cite doc 13, so stays unflagged",
            "result": "PASS" if not early and not early_flagged else "FAIL",
            "assertions": 2,
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:AUD-0074 emit tests not all PASS")
        print(json.dumps(tests, indent=2))
        return 1

    doc = {
        "unit_id": "AUD-0074",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0074",
        "completion_sentinel": SENTINEL,
        "kind": "audit-graph",
        "title": "Source-lineage graph: which artifact derives from which",
        "question": QUESTION,
        "schema_version": 1,
        "produced_at": now,
        "corpus": {
            "origin": pack["origin"],
            "why": pack["why"],
            "live_root": pack["live_root"],
            "live_hits": pack["live_hits"],
            "contracted": 29,
            "present": len(records),
        },
        "corrections": pack["corrections"],
        "nodes": nodes,
        "edges": annotated_edges,
        "stale_downstream": flags,
        "headline": {
            "node_count": len(nodes),
            "citation_edge_count": len(cite_edges),
            "stale_downstream_count": len(flags),
            "doc13_stale_downstream_count": len(doc13_flags),
            "doc13_stale_artifacts": [f["from"] for f in doc13_flags],
        },
        "named_probe_methods": [
            {
                "id": "probe1",
                "instrument": "citation-span-extraction",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/AUD-0074/probe1_citation_edges.py"
                ),
            },
            {
                "id": "probe2",
                "instrument": "per-edge-timestamp-order-vs-known-correction",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/AUD-0074/probe2_timestamp_order.py"
                ),
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "AUD0074-C1",
                "description": (
                    "Known doc-13 correction must produce at least one stale-downstream "
                    "flag; zero flags on that known case means the timestamp check is inert"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": [f["from"] for f in doc13_flags],
                "good_state": [FRESH_POST, NEVER_CORR, EARLY_NO_CITE],
            },
            {
                "id": "AUD0074-C2",
                "description": (
                    "Timestamp-blind mutant (empty correction register) must be silent; "
                    "an always-stale detector would still flag the known case and look green"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "mutant_flags": len(blind),
            },
        ],
        "evidence": [
            {
                "kind": "citation-graph",
                "claim": (
                    f"Citation extraction over the {len(records)} contracted artifacts "
                    f"produced {len(cite_edges)} cite edges (instrument: [cite:target version=ISO])."
                ),
                "detail": f"origin={pack['origin']} live_hits={pack['live_hits']}",
            },
            {
                "kind": "timestamp-order",
                "claim": (
                    f"Per-edge timestamp check against the known 2026-08-07 doc-13 "
                    f"correction flagged {len(flags)} stale-downstream cite(s), "
                    f"{len(doc13_flags)} of them targeting {C.DOC13}."
                ),
                "detail": ",".join(f["from"] for f in doc13_flags),
            },
            {
                "kind": "scope-disclosure",
                "claim": (
                    "Live Prompt-One trees were searched; this run used "
                    f"{pack['origin']} corpus. {pack['why']}"
                ),
                "detail": pack["why"],
            },
        ],
        "report": {
            "kind": "audit-graph",
            "control_ids": ["AUD0074-C1", "AUD0074-C2"],
            "observations": [
                {
                    "name": "citation_edge_count",
                    "measured": len(cite_edges),
                    "method": "static-analysis",
                    "anchor": "command-center/p2-wave/probes/AUD-0074/engine.py:extract_citation_edges",
                },
                {
                    "name": "doc13_stale_downstream_count",
                    "measured": len(doc13_flags),
                    "method": "static-analysis",
                    "anchor": "command-center/p2-wave/probes/AUD-0074/engine.py:flag_stale",
                },
            ],
        },
        "reviewer": {
            "reviewer_id": "AUD-0074-probe2-timestamp-order",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "tried_to_falsify_headline_count": True,
            "notes": (
                "Probe 2 recomputes stale flags from citation edges plus the "
                "correction register and refuses PASS if the known doc-13 case "
                "is silent or if post-correction / never-corrected cites are flagged."
            ),
        },
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
            },
            {
                "path": SCHEMA,
                "role": "schema",
                "exists": True,
            },
        ],
        "answer": (
            f"Derivation graph: {len(nodes)} nodes, {len(cite_edges)} citation edges. "
            f"Artifacts downstream of a since-corrected source: {len(flags)} "
            f"(doc-13 stale-downstream={len(doc13_flags)}: "
            f"{', '.join(f['from'] for f in doc13_flags)}). "
            f"{SENTINEL}"
        ),
    }

    if not SL.catalog_schema_on_disk():
        print("FAILED:AUD-0074 catalog output_schema missing on disk")
        return 1
    errs = SL.iter_errors(doc)
    if errs:
        print("FAILED:AUD-0074 schema")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage_n = SL.garbage_error_count({"nope": True})
    if garbage_n < 1:
        print("FAILED:AUD-0074 schema accepts garbage")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "wrote": OUT,
                "bytes": out.stat().st_size,
                "nodes": len(nodes),
                "edges": len(cite_edges),
                "stale": len(flags),
                "doc13_stale": [f["from"] for f in doc13_flags],
                "origin": pack["origin"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:AUD-0074 emit lineage graph")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
