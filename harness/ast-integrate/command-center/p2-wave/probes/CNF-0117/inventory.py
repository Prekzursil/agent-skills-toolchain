#!/usr/bin/env python3
"""Permission and credential dependency inventory for CNF-0117.

Credentials are denied by unsetting a variable in a subprocess environment.
Real credential files are never opened, written, rotated, or printed.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "CNF-0117"
OUT_REL = "command-center/confirmation/CNF-0117-loud-degradation.json"
SCHEMA_REL = "command-center/schema/permission-report.schema.json"
CONSUMER = HERE / "consumer.py"
TOKEN_ENV = "CNF_0117_TOKEN"
TOKEN_VALUE = "cnf-0117-fixture-token-not-a-live-credential"
CATALOG_ENV = "CNF_0117_CATALOG"
ENRICH_ENV = "CNF_0117_ENRICH_DIR"
FIXTURES = HERE / "fixtures"
MINI_CATALOG = FIXTURES / "catalog.min.json"
DISPATCH = REPO / "command-center/p2-wave/seed-stage/dispatch_cursor.py"

DEPS = (
    {
        "id": "cred-fixture-token",
        "kind": "credential",
        "name": TOKEN_ENV,
        "deny_method": "unset-variable-in-subprocess",
        "capability_token": f"credential:{TOKEN_ENV}",
        "subject": "consumer",
    },
    {
        "id": "perm-catalog-read",
        "kind": "permission",
        "name": "catalog-read",
        "deny_method": "point-catalog-at-absent-path",
        "capability_token": "permission:catalog-read",
        "subject": "consumer",
    },
    {
        "id": "perm-enrichment-write",
        "kind": "permission",
        "name": "enrichment-write",
        "deny_method": "point-enrich-path-at-non-directory",
        "capability_token": "permission:enrichment-write",
        "subject": "consumer",
    },
    {
        "id": "cred-cursor-api-key",
        "kind": "credential",
        "name": "CURSOR_API_KEY",
        "deny_method": "unset-variable-in-subprocess",
        "capability_token": "CURSOR_API_KEY",
        "subject": "dispatch_cursor",
    },
)


def catalog_row() -> dict:
    data = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UNIT:
            return unit
    raise KeyError(UNIT)


def sentinel() -> str:
    return str(catalog_row()["completion_sentinel"])


def inventory_public() -> list[dict]:
    return [
        {
            "id": d["id"],
            "kind": d["kind"],
            "name": d["name"],
            "deny_method": d["deny_method"],
        }
        for d in DEPS
    ]
