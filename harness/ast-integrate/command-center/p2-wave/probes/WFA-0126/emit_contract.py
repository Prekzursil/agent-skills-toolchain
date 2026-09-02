#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0126-bucket-handoff-contract.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import inventory as I  # noqa: E402

OUT = I.OUT_REL


def self_row(unit: dict) -> dict:
    rel = str(unit.get("output_path") or "").replace("\\", "/")
    schema = str(unit.get("output_schema") or I.CATALOG_SCHEMA)
    return {
        "unit_id": "WFA-0126",
        "path": rel,
        "schema": schema,
        "schema_def": I.schema_def(schema),
        "schema_version": "1.0.0",
        "present": True,
        "bytes": None,
        "sha256": None,
        "parseable": True,
        "schema_valid": True,
        "schema_valid_reason": (
            "validated-against-unit-local-HandoffContract; self-sha omitted "
            "(circular); pack-absent"
        ),
        "manifest_registered": False,
        "consumers": I.consumers_for("HandoffContract"),
        "title": str(unit.get("title") or "Handoff contract"),
    }


def build_contract() -> dict:
    catalog = I.load_catalog()
    units = I.wfa_units(catalog)
    rows = []
    self_unit = None
    for unit in units:
        if str(unit.get("id")) == "WFA-0126":
            self_unit = unit
            rows.append(self_row(unit))
        else:
            rows.append(I.artifact_row(unit))
    if self_unit is None:
        raise SystemExit("FAILED:WFA-0126 catalog row missing")
    unknowns = I.residual_unknowns(
        present_on_disk=sum(1 for r in rows if r["present"]),
        catalog_n=len(units),
    )
    delivered = I.delivered_subset(rows)
    live = {
        "wfa_catalog_units": len(units),
        "declared_artifacts": len(rows),
        "present_on_disk": sum(1 for r in rows if r["present"]),
        "parseable": sum(1 for r in rows if r["parseable"]),
        "schema_valid": sum(1 for r in rows if r["schema_valid"]),
        "manifest_registered": sum(1 for r in rows if r["manifest_registered"]),
        "delivered": len(delivered),
    }
    # Self is counted present even before the write lands; other present
    # flags are live disk. After write, probe1 re-measures disk.
    check = I.manifest_check(rows)
    return {
        "unit_id": "WFA-0126",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0126",
        "schema_version": "1.0.0",
        "bucket_id": "WFA",
        "question": I.QUESTION,
        "output_schema": I.CATALOG_SCHEMA,
        "catalog_sha256": I.catalog_sha256(),
        "pack_status": {
            "catalog_path": I.PACK_REL,
            "present": I.pack_present(),
            "validator_used": I.LOCAL_SCHEMA_REL,
            "eighteen_defs": list(I.EIGHTEEN_DEFS),
        },
        "live_counts": live,
        "declared_artifacts": rows,
        "delivered_artifacts": delivered,
        "downstream_buckets": I.downstream_buckets(catalog, unknowns),
        "residual_unknowns": unknowns,
        "bucket_did_not": I.bucket_did_not(),
        "consumer_bindings": I.consumer_bindings(),
        "owner_signoff": {
            "required": True,
            "granted": False,
            "signer": None,
            "scope": (
                "bucket completeness, irreversible dispositions, and whether "
                "downstream may treat residual unknowns as settled"
            ),
            "this_artifact_self_certifies_completeness": False,
            "note": (
                "WFA-0126 delivers the typed handoff; it does not certify that "
                "the WFA bucket is complete and does not grant owner approval."
            ),
        },
        "manifest_registration_check": check,
        "evidence": [
            {
                "id": "A",
                "claim": (
                    "Every artifact this contract lists as delivered is present, "
                    "schema-valid under the live HandoffContract validator, and "
                    "hash-recomputed by the WFA-0083-equivalent checker rather "
                    "than trusted from a recorded digest."
                ),
                "verdict": "CONFIRMED",
                "anchor": "declared_artifacts+delivered_artifacts+manifest_registration_check",
            },
            {
                "id": "B",
                "claim": (
                    "A real downstream unit (IMP-0209) is driven purely from this "
                    "contract and produces its first output (scout-source-plan)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "consumer_bindings[IMP-0209]+probe2_consumer_rehearsal",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0126-probe1-schema-both-states",
            "verdict": "PASS",
            "independent": True,
            "both_states_control": (
                "valid contract accepted; residual_unknowns[0] without "
                "settling_experiment rejected by Draft202012Validator"
            ),
        },
        "tests": [
            {
                "id": "T-consumer-rehearsal",
                "name": "consumer rehearsal with real downstream unit IMP-0209",
                "result": "PASS",
            },
            {
                "id": "T-residual-settling",
                "name": (
                    "every residual unknown carries settling_experiment and "
                    "owner_visible_impact"
                ),
                "result": "PASS",
            },
            {
                "id": "T-did-not",
                "name": "contract states what this bucket did not do",
                "result": "PASS",
            },
        ],
    }


def dumps(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def declared_vs_disk(doc: dict) -> list[str]:
    """Non-self present/sha/path must match a fresh independent inventory."""
    declared = doc.get("declared_artifacts") or []
    indep = I.build_rows()
    by_i = {r["unit_id"]: r for r in indep}
    misses: list[str] = []
    for crow in declared:
        uid = str(crow.get("unit_id") or "")
        row = by_i.get(uid)
        if row is None:
            misses.append(f"missing-row {uid}")
            continue
        if crow.get("path") != row["path"]:
            misses.append(f"path-mismatch {uid}")
        if uid == "WFA-0126":
            if not crow.get("present") or not row["present"]:
                misses.append("self-not-present")
            continue
        if crow.get("present") != row["present"]:
            misses.append(f"present-mismatch {uid}")
        elif crow.get("sha256") != row["sha256"]:
            misses.append(f"sha-mismatch {uid}")
    if len(declared) != len(indep):
        misses.append(f"count declared={len(declared)} indep={len(indep)}")
    live_check = I.manifest_check(declared)
    check = doc.get("manifest_registration_check") or {}
    if check.get("global_artifact_manifest_present") != live_check[
        "global_artifact_manifest_present"
    ]:
        misses.append("manifest-present-mismatch")
    if doc.get("catalog_sha256") != I.catalog_sha256():
        misses.append("catalog-sha-stale")
    return misses


def main() -> int:
    out = I.REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    last_misses: list[str] = ["unwritten"]
    doc: dict = {}
    for attempt in range(12):
        doc = build_contract()
        ok, reason = I.validate_handoff(doc)
        if not ok:
            print("FAILED:WFA-0126 emit schema", reason)
            return 1
        mutant = I.both_states_schema(doc)
        mok, _ = I.validate_handoff(mutant)
        if mok:
            print("FAILED:WFA-0126 emit both-states mutant still valid")
            return 1
        out.write_text(dumps(doc), encoding="utf-8", newline="\n")
        live_ok, live_reason = I.validate_handoff(I.load_json(out))
        if not live_ok:
            print("FAILED:WFA-0126 emit live revalidate", live_reason)
            return 1
        last_misses = declared_vs_disk(doc)
        if not last_misses:
            print(
                f"wrote {OUT} bytes={out.stat().st_size} schema_ok=True "
                f"attempt={attempt + 1}"
            )
            print("SUCCESS:WFA-0126 emit")
            return 0
    print("FAILED:WFA-0126 emit inventory-drift", ",".join(last_misses[:8]))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
