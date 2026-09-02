#!/usr/bin/env python3
"""Probe 1: schema discrimination + record-count arithmetic + both-states."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import registry_lib as L  # noqa: E402


def main() -> int:
    out = L.REPO / L.OUT_REL
    fixture = L.REPO / L.V1_FIXTURE_REL
    catalog_pack = L.REPO / L.SCHEMA_REL
    unit_schema = L.REPO / L.UNIT_SCHEMA_REL
    if not out.is_file() or not fixture.is_file() or not catalog_pack.is_file():
        print("FAILED:WFA-0078-probe1 missing artifact/schema/v1-fixture")
        return 1
    live_pack = L.load_json(catalog_pack)
    if "WorkflowRecord" not in (live_pack.get("$defs") or {}):
        print("FAILED:WFA-0078-probe1 catalog schema missing WorkflowRecord")
        return 1
    artifact = L.load_json(out)
    v1 = L.load_json(fixture)
    pack = L.schema_pack()
    if unit_schema.is_file():
        disk_pack = L.load_json(unit_schema)
        if disk_pack.get("$defs", {}).get("WorkflowRecord") != pack["$defs"]["WorkflowRecord"]:
            print("FAILED:WFA-0078-probe1 unit-local schema drifted from schema_pack()")
            return 1

    if artifact.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:WFA-0078-probe1 self-declared {artifact.get('state')}")
        return 1
    if L.SENTINEL not in json.dumps(artifact):
        print("FAILED:WFA-0078-probe1 sentinel absent")
        return 1

    errs = L.validate_against(pack, artifact)
    if errs:
        print("FAILED:WFA-0078-probe1 schema")
        print("\n".join(errs[:12]))
        return 1

    rec_schema = {
        "$schema": pack["$schema"],
        **pack["$defs"]["WorkflowRecord"],
    }
    for rec in artifact["records"]:
        rerr = L.validate_against(rec_schema, rec)
        if rerr:
            print(f"FAILED:WFA-0078-probe1 record {rec.get('id')}")
            print("\n".join(rerr[:8]))
            return 1

    garbage = {"totally": "unrelated", "passing_tests": 999999}
    gerr = L.validate_against(pack, garbage)
    if not gerr:
        print("FAILED:WFA-0078-probe1 schema accepts garbage")
        return 1

    mutant = copy.deepcopy(artifact["records"][0])
    del mutant["id"]
    merr = L.validate_against(rec_schema, mutant)
    if not merr:
        print("FAILED:WFA-0078-probe1 missing-id still valid")
        return 1

    ok, detail = L.arithmetic_ok(artifact, v1)
    if not ok:
        print(f"FAILED:WFA-0078-probe1 arithmetic {detail}")
        return 1

    live_sha, _ = L.sha256_file(fixture)
    if artifact.get("v1", {}).get("sha256") != live_sha:
        print("FAILED:WFA-0078-probe1 v1 sha mismatch vs frozen fixture")
        return 1
    if artifact.get("v1", {}).get("unmodified") is not True:
        print("FAILED:WFA-0078-probe1 v1.unmodified is not true")
        return 1

    print(
        json.dumps(
            {
                "arithmetic": detail,
                "garbage_rejected": True,
                "missing_id_rejected": True,
                "records": artifact["arithmetic"]["v2_count"],
                "schema_ok": True,
                "v1_sha256": live_sha,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0078-probe1 schema-arithmetic both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
