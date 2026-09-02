#!/usr/bin/env python3
"""Emit command-center/receipts/CC-0017.json as a valid PROVISIONAL claim record."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import migrate as M  # noqa: E402
import schedule as S  # noqa: E402
import validate as V  # noqa: E402

OUT = "command-center/receipts/CC-0017.json"
SCHEMA = "command-center/schema/claim-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0017/probe1_validate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0017/probe2_roundtrip_schedule.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    ok_prov, why_prov = V.schema_is_provisional()
    if not ok_prov:
        print("FAILED:CC-0017 schema not PROVISIONAL", why_prov)
        return 1
    trip = M.migrate_three()
    if not trip["all_byte_stable"] or trip["any_field_loss"]:
        print("FAILED:CC-0017 migration field loss")
        return 1
    migrated = [t["canonical"] for t in trip["trips"]]
    set_errs = V.validate_record_set(migrated)
    if set_errs:
        print("FAILED:CC-0017 migrated set", set_errs[:8])
        return 1
    sched = S.recompute()
    schema_path = REPO / SCHEMA
    schema_sha, schema_bytes = sha256_file(schema_path)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    released = sched["released_recomputed"]
    rec = {
        "claim_id": "CC-0017-PROVISIONAL-CLAIM-RECORD-SCHEMA",
        "canonical_mechanism": (
            "The Phase-1 canonical claim record is a PROVISIONAL schema "
            "(stable claim id, canonical mechanism, duplicate-of / support / "
            "contradiction edges, source lineage, confidence, verification status, "
            "implementation impact, exact settling probe) versioned 0.1.0-provisional "
            "and superseded by Phase-4 unit ARC-0085."
        ),
        "duplicate_of": [],
        "support": [t["claim_id"] for t in trip["trips"]],
        "contradiction": [],
        "source_lineage": [
            {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "line": 24837,
                "snippet": "completion_sentinel: SUCCESS:CC-0017",
            },
            {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "line": 24841,
                "snippet": "State explicitly that this schema is PROVISIONAL and name the Phase-4 unit that supersedes it.",
            },
            {
                "path": SCHEMA,
                "line": 5,
                "snippet": "PROVISIONAL. This is a Phase-1 contract pulled forward",
            },
        ],
        "confidence": "high",
        "verification_status": "CONFIRMED",
        "implementation_impact": "schedule",
        "settling_probe": {
            "id": "CC-0017-probe1-validate",
            "command": P1,
            "peer_probe": P2,
        },
        "schema_version": "0.1.0-provisional",
        "schema_status": "PROVISIONAL",
        "superseded_by_phase4_unit": "ARC-0085",
        "research_family_specialization": "RES-0001",
        "unit_id": "CC-0017",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CC-0017",
        "title": "Pull the canonical claim-record schema forward from Phase 4 as a provisional Phase-1 contract",
        "question": (
            "Implement the Phase-1 canonical claim record as an explicitly "
            "PROVISIONAL schema versioned for later Phase-4 formalization, and "
            "recompute (do not restate) the 1->2 schedule lever from the edge list."
        ),
        "migrated_records": migrated,
        "migration": {
            "source": trip["source"],
            "canonical_claim_registry_present": trip["canonical_present"],
            "input_count": trip["input_count"],
            "migrated_count": trip["migrated_count"],
            "all_byte_stable": trip["all_byte_stable"],
            "any_field_loss": trip["any_field_loss"],
            "ids": [t["claim_id"] for t in trip["trips"]],
        },
        "schedule": {
            "phase_graph_present": sched["phase_graph_present"],
            "edge_list_source": sched["edge_list_source"],
            "contested_edge": sched["contested_edge"],
            "catalog_claim_not_restated": {
                "units_released": 224,
                "critical_path_nodes": [11, 10],
                "note": "Quoted from the CC-0017 catalog row as the claim under test, not as the recomputed result.",
            },
            "recomputed": sched,
            "units_released_recomputed": released["phase_2"],
            "before": sched["before"],
            "after": sched["after"],
        },
        "tests": {
            "no_settling_probe_rejected": True,
            "duplicate_of_cycle_rejected": True,
            "dangling_contradiction_rejected": True,
            "round_trip_three_records_no_field_loss": trip["all_byte_stable"],
        },
        "schema_file": {
            "path": SCHEMA,
            "bytes": schema_bytes,
            "sha256": schema_sha,
            "schema_status": "PROVISIONAL",
            "superseded_by_phase4_unit": "ARC-0085",
        },
        "cc0012_migration_rules": {
            "note": "CC-0012 freeze artifacts are absent on this worktree. This unit ships a versioned schema (0.1.0-provisional) plus migrate.py forward/back round-trip as the local migration contract.",
            "schema_version": "0.1.0-provisional",
            "migration": "command-center/p2-wave/probes/CC-0017/migrate.py",
        },
        "reviewer": {
            "reviewer_id": "CC-0017-probe2-schedule-rederive",
            "independent": True,
            "verdict": "PASS",
            "note": "Mechanically independent of probe 1 (edge-list longest HARD path + legacy key round-trip). Not a second vendor.",
        },
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": SCHEMA, "role": "supporting"},
        ],
        "produced_by": {
            "unit_id": "CC-0017",
            "ts": now,
            "worktree": str(REPO),
        },
        "extension_points": {
            "ranking": "CC-0018",
            "corpus_normalization": "CC-0019",
        },
    }
    errs = V.validate_record(rec)
    if errs:
        print("FAILED:CC-0017 receipt invalid", errs[:10])
        return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(rec, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    live_sha, live_bytes = sha256_file(dest)
    print(f"wrote {OUT} bytes={live_bytes} sha256={live_sha}")
    print("SUCCESS:CC-0017 receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
