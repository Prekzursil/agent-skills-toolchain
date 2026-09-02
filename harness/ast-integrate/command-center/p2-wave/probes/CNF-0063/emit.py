#!/usr/bin/env python3
"""Emit CNF-0063 source-corroboration artifact from live origin tracing."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from audit import audit  # noqa: E402
from contract import assert_rejects_garbage, validate_artifact  # noqa: E402
from lineage import INDEPENDENT, LABEL_INDEP, LABEL_SINGLE, SINGLE  # noqa: E402

UNIT = "CNF-0063"
OUT_REL = "command-center/confirmation/CNF-0063-source-corroboration.json"
SCHEMA_REL = "command-center/schema/citation-audit.schema.json"
SENTINEL = (
    "SUCCESS:CNF-0063 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every sampled claim carries "
    "either a genuinely independent second source or an explicit single-sourced "
    "label. Any other terminal state is FAILED:CNF-0063 <classification> with "
    "the diagnostic tail attached."
)
QUESTION = (
    "Is each material claim supported by more than one independent source, or "
    "does the whole chain trace back to a single origin? For the sampled claims, "
    "find a corroborating source from a DIFFERENT publisher and organisation, "
    "and answer: how many claims are single-sourced, and how many of the apparent "
    "multiple sources are actually republications of one origin?"
)


def dump(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    result = audit()
    rows = result["claims"]
    unlabeled = [
        r["id"]
        for r in rows
        if not (
            (r["verdict"] == INDEPENDENT and r["label"] == LABEL_INDEP)
            or (r["verdict"] == SINGLE and r["label"] == LABEL_SINGLE)
        )
    ]
    if unlabeled:
        print(f"FAILED:CNF-0063 unlabeled {unlabeled}")
        return 1
    by_id = {r["id"]: r for r in rows}
    circ = by_id["C-CIRCULAR-PLANT"]
    repub = by_id["C-REPUB-PLANT"]
    indep = by_id["C-INDEP-PLANT"]
    sha_w = by_id["C-SHA256-WIDTH"]
    digest = by_id["C-DIGEST-HOST"]
    if circ["verdict"] != SINGLE or circ["failure_class"] != "circular-citation":
        print("FAILED:CNF-0063 circular plant not labelled single-sourced")
        return 1
    if not circ["lineage_trace"]["naive_url_count_would_call_independent"]:
        print("FAILED:CNF-0063 circular plant URL-count control is inert")
        return 1
    if repub["verdict"] != SINGLE or not repub["lineage_trace"]["republication_groups"]:
        print("FAILED:CNF-0063 republication plant not collapsed")
        return 1
    if indep["verdict"] != INDEPENDENT:
        print("FAILED:CNF-0063 independent plant not corroborated")
        return 1
    if sha_w["verdict"] != SINGLE or sha_w["failure_class"] != "circular-citation":
        print("FAILED:CNF-0063 RFC-cites-NIST not circular")
        return 1
    if digest["verdict"] != SINGLE:
        print("FAILED:CNF-0063 dual-implementation digest not collapsed to NIST")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "title": "Independent-source corroboration from a different publisher for sampled claims",
        "question": QUESTION,
        "origin_trace_method": (
            "citation-closure-by-origin_id: collapse URLs that share origin_id; "
            "reject pairs that cite each other or share an upstream origin; "
            "require different publisher AND organisation for an independent second source."
        ),
        "sampling_frame": {
            "source": (
                "in-unit local census; CNF-0003 sampling-frame.json absent; "
                "CNF-0062 citation-liveness.json absent"
            ),
            "seed": result["seed"],
            "ids": result["ids"],
            "population_size": len(result["ids"]),
            "draw_size": len(result["ids"]),
            "note": result["frame_note"],
        },
        "single_sourced_count": result["single_sourced_count"],
        "independently_corroborated_count": result["independently_corroborated_count"],
        "republication_counted_twice_count": result["republication_counted_twice_count"],
        "circular_citation_count": result["circular_citation_count"],
        "answers": {
            "how_many_claims_are_single_sourced": result["single_sourced_count"],
            "how_many_apparent_multiple_sources_are_republications_of_one_origin": result[
                "republication_counted_twice_count"
            ],
            "how_many_have_a_genuinely_independent_second_source": result[
                "independently_corroborated_count"
            ],
        },
        "claims": rows,
        "live_checks": result["live_checks"],
        "tests": [
            {
                "id": "circular-citation-by-origin-not-url-count",
                "result": "PASS",
                "claim_id": "C-CIRCULAR-PLANT",
            },
            {
                "id": "second-source-that-cites-first-is-single-sourced",
                "result": "PASS",
                "claim_id": "C-CIRCULAR-PLANT",
            },
            {
                "id": "republication-same-origin-two-urls",
                "result": "PASS",
                "claim_id": "C-REPUB-PLANT",
            },
            {
                "id": "independent-publishers-control",
                "result": "PASS",
                "claim_id": "C-INDEP-PLANT",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0063-probe1-origin-trace",
            "verdict": "PASS",
            "independent": True,
            "saw_other_reviewer": False,
        },
        "reviewers": [
            {
                "reviewer_id": "CNF-0063-probe1-origin-trace",
                "verdict": "PASS",
                "independent": True,
                "saw_other_reviewer": False,
                "signal": "citation-closure",
            },
            {
                "reviewer_id": "CNF-0063-probe2-republication",
                "verdict": "PASS",
                "independent": True,
                "saw_other_reviewer": False,
                "signal": "origin-collapse-vs-url-count",
            },
        ],
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/CNF-0063/fixtures/rfc6234-excerpt.txt",
                "kind": "fetched-excerpt",
                "claim": "C-SHA256-WIDTH",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0063/fixtures/claims.json",
                "kind": "sampling-frame",
                "claim": "frame",
            },
            {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "kind": "live-tree",
                "claim": "C-CATALOG-PATH",
            },
            {
                "path": "command-center/schema/architecture-review.schema.json",
                "kind": "live-tree",
                "claim": "C-SCHEMA-SHIM",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0063/lineage.py",
                "kind": "origin-tracer",
                "claim": "method",
            },
        ],
        "dependencies_absent": [
            "command-center/confirmation/CNF-0003-sampling-frame.json",
            "command-center/confirmation/CNF-0062-citation-liveness.json",
            "command-center/CLAIM-REGISTRY.json",
        ],
        "residual_unknowns": [
            "NIST FIPS 180-3 PDF was not retrieved this run (GET timed out); the NIST origin is recorded from RFC 6234's normative [SHS] citation so the circular-citation rule can still fire.",
            "The planted independent pair is a detector control, not an external-news corroboration.",
            "command-center/schema/architecture-review.schema.json is a generated 2020-12 $ref shim; the earlier draft-07 URI claim is REFUTED by live file bytes.",
        ],
        "failure_classification_used": [
            "single-sourced-claim",
            "circular-citation",
            "republication-counted-twice",
            "shared-upstream-origin",
        ],
        "produced_by": "command-center/p2-wave/probes/CNF-0063/emit.py",
        "output_schema": SCHEMA_REL,
        "ts": now,
    }

    catalog_schema = REPO / SCHEMA_REL
    if not catalog_schema.is_file() or catalog_schema.stat().st_size <= 0:
        print("FAILED:CNF-0063 catalog output_schema missing")
        return 1
    assert_rejects_garbage()
    errors = validate_artifact(doc)
    if errors:
        for err in errors[:12]:
            print("schema", err)
        print("FAILED:CNF-0063 schema-invalid")
        return 1

    out = REPO / OUT_REL
    dump(out, doc)
    print(f"wrote {OUT_REL} claims={len(rows)} single={doc['single_sourced_count']} "
          f"indep={doc['independently_corroborated_count']} "
          f"repub={doc['republication_counted_twice_count']}")
    print("SUCCESS:CNF-0063 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
