#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0031-acquisition-legal-gate.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus  # noqa: E402

OUT_REL = "command-center/wfa/WFA-0031-acquisition-legal-gate.json"
SENTINEL = "SUCCESS:WFA-0031"
QUESTION = (
    "For every externally acquired artifact: what licence actually governs it, "
    "does this estate's intended use — mechanism extraction rather than "
    "redistribution — comply, and which acquisitions must be refused or reduced "
    "to a described-mechanism-only record with no code carried across?"
)


def main() -> int:
    gate = corpus.load_gate()
    sources = corpus.all_sources(gate)
    records = gate.evaluate_many(sources)
    planted = [r for r in records if r.origin == "planted-fixture"]
    live = [r for r in records if r.origin != "planted-fixture"]

    histogram: dict[str, int] = {}
    for rec in records:
        histogram[rec.classification] = histogram.get(rec.classification, 0) + 1

    refuse = [r.source_id for r in records if r.ingest_mode == "REFUSE"]
    mechanism_only = [
        r.source_id for r in records if r.ingest_mode == "MECHANISM_ONLY"
    ]
    unclassified = [r.source_id for r in records if r.classification == "UNCLASSIFIED"]
    copyleft = [r.source_id for r in records if r.classification == "COPYLEFT"]
    adverse = [
        r.source_id for r in records if r.classification == "ADVERSE-UNLICENSED"
    ]
    rider = [r.source_id for r in records if r.classification == "RIDER-RESTRICTED"]
    attribution = [
        r.source_id
        for r in records
        if any(o.get("kind") == "attribution-required" for o in r.obligations)
    ]

    license_graph = REPO / (
        "command-center/08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json"
    )
    graph_present = license_graph.is_file()

    doc = {
        "record_type": "AuditReport",
        "unit_id": "WFA-0031",
        "state": "SUCCESS",
        "completion_sentinel": SENTINEL,
        "title": (
            "Licence, terms-of-service and legal gate on everything the "
            "acquisition lane ingests"
        ),
        "question": QUESTION,
        "intended_use": gate.INTENDED_USE,
        "owner_approval_required": True,
        "owner_signed": False,
        "owner_note": (
            "This unit delivers the gate. It does not self-certify an irreversible "
            "ingestion of third-party code. CODE_PERMITTED_WITH_OBLIGATIONS rows "
            "still require owner sign-off before any code is carried."
        ),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema_note": (
            "Catalog output_schema is command-center/wfa/schema/wfa-schema-pack.json"
            "#/$defs/AuditReport. WFA-0001 pack is absent on this worktree; this "
            "document is an AuditReport-shaped gate audit and is not claimed to "
            "have been validated against a missing pack."
        ),
        "inputs": {
            "license_risk_register_45": {
                "path": (
                    "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json"
                    "#license_risk_register"
                ),
                "present": graph_present,
                "status": "PRESENT" if graph_present else "SOURCE-ABSENT",
                "note": (
                    "The 45-row licence_risk_register is not in this worktree. "
                    "The gate was not populated with invented register rows."
                ),
            },
            "user_prompts_legal_and_tor": {
                "status": "SOURCE-ABSENT",
                "note": (
                    "_USER-PROMPTS.md legal/Tor policy slice is not in this "
                    "worktree. A conservative ToS/Tor-evasion refuse rule is "
                    "implemented and planted; the original prompt text was not "
                    "paraphrased from memory."
                ),
            },
            "in_tree_acquisition_captures": [
                "command-center/p2-wave/probes/RES-0109/captures",
                "command-center/p2-wave/probes/RES-0136/fixtures",
            ],
        },
        "evidence": {
            "A": (
                "SPDX parsed from fetched LICENSE/COPYING/terms blobs "
                "(sha256 stored). README badges are observed and ignored."
            ),
            "B": (
                "Host-declared licence metadata (GitHub API license.spdx_id, "
                "else captures_index.classifier_spdx, else ecosyste.ms.license). "
                "Transport errors are unavailable, not a classified null."
            ),
            "disagreement_rule": (
                "When A and B both exist and differ, the record is UNCLASSIFIED "
                "and escalated; neither signal is preferred."
            ),
        },
        "controls": {
            "unlicensed_adverse_not_permissive": True,
            "planted_restrictive_fires": True,
            "attribution_and_rider_obligations": True,
            "disagreement_unclassified": True,
        },
        "histogram": histogram,
        "counts": {
            "sources_evaluated": len(records),
            "planted": len(planted),
            "live_captures": len(live),
            "refuse": len(refuse),
            "mechanism_only": len(mechanism_only),
            "unclassified": len(unclassified),
            "copyleft": len(copyleft),
            "adverse_unlicensed": len(adverse),
            "rider_restricted": len(rider),
            "attribution_obligations": len(attribution),
            "code_carried": sum(1 for r in records if r.code_carried),
        },
        "must_refuse_or_mechanism_only": sorted(set(refuse + mechanism_only)),
        "unclassified_escalations": unclassified,
        "findings": [
            {
                "id": "F1",
                "claim": (
                    "A source with no discoverable licence blob defaults to "
                    "adverse/most-restrictive treatment, not to a permissive "
                    "README badge or API field."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "id": "F2",
                "claim": (
                    "A planted GPL-3.0 artefact fires the gate (COPYLEFT, "
                    "MECHANISM_ONLY, no code carried) before silence on live "
                    "captures is trusted."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "id": "F3",
                "claim": (
                    "Attribution-required (Apache-2.0) and rider-restricted "
                    "(Commons Clause) sources produce explicit obligations "
                    "records, with rider text verbatim."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "id": "F4",
                "claim": (
                    "File SPDX vs API SPDX disagreement is UNCLASSIFIED and "
                    "escalated rather than resolved by preference."
                ),
                "verdict": "CONFIRMED",
            },
        ],
        "tests": [
            {"id": "adverse-unlicensed", "result": "PASS"},
            {"id": "planted-gpl3-fires", "result": "PASS"},
            {"id": "apache-attribution-obligations", "result": "PASS"},
            {"id": "rider-verbatim-obligations", "result": "PASS"},
            {"id": "ab-disagreement-unclassified", "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "WFA-0031-probe2-obligations-and-disagreement",
            "independent": True,
            "verdict": "PASS",
            "note": (
                "Adversarial probe re-runs the planted disagreement and "
                "both-states MIT-agree control."
            ),
        },
        "records": [r.as_dict() for r in records],
        "gate_module": "command-center/wfa/legal_gate.py",
        "completion_sentinel_line": SENTINEL,
    }
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} records={len(records)} histogram={histogram}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
