#!/usr/bin/env python3
"""Inventory catalog artifact classes and pick one sample per class."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PLANTED_CLASS = "planted-unconsumed"
PLANTED_SAMPLE = (
    "command-center/p2-wave/probes/CNF-0123/fixtures/planted-unconsumed.json"
)
PLANTED_SCHEMA = (
    "command-center/p2-wave/probes/CNF-0123/fixtures/planted-unconsumed.json"
)
RECEIPT_FIXTURE = (
    "command-center/p2-wave/probes/CNF-0123/fixtures/receipt-sample.json"
)
SELF_OUTPUT = "command-center/confirmation/CNF-0123-downstream-readability.json"
SELF_SCHEMA = "command-center/schema/conformance-report.schema.json"


def class_id_from_schema(schema: str) -> str:
    s = str(schema or "").replace("\\", "/").strip()
    if not s:
        return "missing-schema"
    s = s.split()[0]
    s = s.split("#")[0]
    s = s.split("?")[0]
    base = s.rsplit("/", 1)[-1]
    base = re.sub(r"\.schema\.json$", "", base, flags=re.I)
    base = re.sub(r"\.json$", "", base, flags=re.I)
    return base or "unknown"


def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def inventory() -> list[dict[str, Any]]:
    cat = load_catalog()
    buckets: dict[str, dict[str, Any]] = {}
    for unit in cat.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id") or "")
        schema = str(unit.get("output_schema") or "")
        cid = class_id_from_schema(schema)
        out = str(unit.get("output_path") or "").replace("\\", "/")
        row = buckets.setdefault(
            cid,
            {
                "class_id": cid,
                "output_schema": schema.split()[0] if schema else "",
                "unit_ids": [],
                "output_paths": [],
            },
        )
        if uid:
            row["unit_ids"].append(uid)
        if out:
            row["output_paths"].append(out)
        if schema and not row["output_schema"]:
            row["output_schema"] = schema.split()[0]

    rows: list[dict[str, Any]] = []
    for cid, raw in sorted(buckets.items(), key=lambda kv: kv[0]):
        sample = None
        source = "none"
        if cid == "conformance-report":
            self_path = REPO / SELF_OUTPUT
            if self_path.is_file() and self_path.stat().st_size > 0:
                sample = SELF_OUTPUT
                source = "self"
                raw["output_schema"] = SELF_SCHEMA
        if sample is None:
            for rel in raw["output_paths"]:
                p = REPO / rel
                if p.is_file() and p.stat().st_size > 0:
                    sample = rel
                    source = "produced"
                    break
        if sample is None and cid == "receipt":
            sample = RECEIPT_FIXTURE
            source = "fixture"
        if sample is None and cid == "conformance-report":
            sample = SELF_OUTPUT
            source = "self"
            raw["output_schema"] = SELF_SCHEMA
        schema_rel = raw["output_schema"]
        schema_exists = bool(schema_rel) and (REPO / schema_rel.split("#")[0]).is_file()
        rows.append(
            {
                "class_id": cid,
                "output_schema": schema_rel,
                "unit_count": len(raw["unit_ids"]),
                "sample_path": sample,
                "sample_source": source,
                "schema_path_exists": schema_exists,
            }
        )

    planted = {
        "class_id": PLANTED_CLASS,
        "output_schema": PLANTED_SCHEMA,
        "unit_count": 0,
        "sample_path": PLANTED_SAMPLE,
        "sample_source": "fixture",
        "schema_path_exists": True,
        "planted_control": True,
    }
    if PLANTED_CLASS not in {r["class_id"] for r in rows}:
        rows.append(planted)
    rows.sort(key=lambda r: r["class_id"])
    return rows


if __name__ == "__main__":
    data = inventory()
    print(json.dumps({"class_count": len(data), "classes": data}, indent=2)[:4000])
    print(f"classes={len(data)}")
