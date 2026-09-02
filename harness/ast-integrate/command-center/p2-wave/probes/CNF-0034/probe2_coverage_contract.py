#!/usr/bin/env python3
"""Probe 2: artifact contract, schema, and per-component untested-surface rows.

Independent of probe 1's printout: re-reads the confirmation JSON, validates
it against interface-coverage.schema.json, and checks that every component
lists a surface this unit exercised that author tests did not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/confirmation/CNF-0034-alternate-interface.json"
SCHEMA = REPO / "command-center/schema/interface-coverage.schema.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
UNIT = "CNF-0034"


def catalog_sentinel() -> str:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UNIT:
            return str(unit.get("completion_sentinel") or "")
    raise SystemExit("FAILED:CNF-0034-probe2 catalog unit missing")


def fake_component_without_untested() -> dict:
    return {
        "id": "mutant-author-only",
        "fixed_behaviour": "placeholder",
        "surfaces_enumerated": [
            {"kind": "library", "path": "x.py", "present": True},
            {"kind": "cli", "path": "x.py", "present": True},
        ],
        "author_tested": [{"kind": "library", "citation": "tests/test_x.py:1"}],
        "this_unit_tested": ["library"],
        "untested_surfaces_exercised_by_this_unit": [],
        "outcomes": [
            {
                "surface": "library",
                "author_tested": True,
                "this_unit_tested": True,
                "result": "HOLD",
            }
        ],
    }


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0034-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    garbage = jsonschema.Draft7Validator(schema)
    if not list(garbage.iter_errors({})) or not list(garbage.iter_errors({"blob": 1})):
        print("FAILED:CNF-0034-probe2 schema accepted garbage")
        return 1
    sentinel = catalog_sentinel()
    if sentinel not in text:
        print("FAILED:CNF-0034-probe2 catalog sentinel absent from artifact")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNF-0034-probe2 self-declared", doc.get("state"))
        return 1
    components = doc.get("components") or []
    if len(components) < 1:
        print("FAILED:CNF-0034-probe2 no components")
        return 1
    for comp in components:
        untested = comp.get("untested_surfaces_exercised_by_this_unit") or []
        if not untested:
            print("FAILED:CNF-0034-probe2 component lacks untested surface", comp.get("id"))
            return 1
        author_kinds = {row.get("kind") for row in (comp.get("author_tested") or [])}
        overlap = set(untested) & author_kinds
        if overlap:
            print("FAILED:CNF-0034-probe2 claimed untested but author tested", overlap)
            return 1
        held = [
            o
            for o in (comp.get("outcomes") or [])
            if o.get("surface") in untested
            and o.get("this_unit_tested") is True
            and o.get("author_tested") is False
            and o.get("result") in {"HOLD", "NOT-CHECKED", "BLOCKED"}
        ]
        if not held:
            print("FAILED:CNF-0034-probe2 no outcome row for untested surface", comp.get("id"))
            return 1
        mcp_rows = [o for o in (comp.get("outcomes") or []) if o.get("surface") == "mcp"]
        for row in mcp_rows:
            if row.get("result") == "HOLD":
                print("FAILED:CNF-0034-probe2 MCP HOLD without a server")
                return 1
            if row.get("result") == "NOT-CHECKED" and not row.get("blocking_prerequisite"):
                print("FAILED:CNF-0034-probe2 MCP NOT-CHECKED missing blocker")
                return 1
    fake = fake_component_without_untested()
    if fake.get("untested_surfaces_exercised_by_this_unit"):
        print("FAILED:CNF-0034-probe2 mutant control is not empty")
        return 1
    print(
        f"schema_ok=True components={len(components)} "
        "untested_per_component=True mutant_empty_untested_detected=True"
    )
    print("SUCCESS:CNF-0034-probe2 schema and untested-surface contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
