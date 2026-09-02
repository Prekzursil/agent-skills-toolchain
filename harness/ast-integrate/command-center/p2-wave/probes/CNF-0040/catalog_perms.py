"""Load declared tool_permissions for the implementing unit from the catalog."""
from __future__ import annotations

import dataclasses
import importlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
IMPLEMENTING_ID = "IMP-0136"
CONFIRMER_ID = "CNF-0040"

SEED_DEFAULTS = [
    "Read",
    "Grep",
    "Glob",
    "Bash",
    "PowerShell",
    "Write",
    "Edit",
]
FULL_EXTRA = [
    "Network",
    "mcp__cloud-hub__modal_sandbox_exec",
]

SOURCE_PATHS = [
    "tools/agentspec/agentspec/dispatchpolicy.py",
    "tools/agentspec/agentspec/spec.py",
]


def load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def unit_by_id(catalog: dict, uid: str) -> dict:
    for item in catalog.get("work_units") or []:
        if isinstance(item, dict) and item.get("id") == uid:
            return item
    raise KeyError(uid)


def implementing(catalog: dict | None = None) -> dict:
    cat = catalog if catalog is not None else load_catalog()
    unit = unit_by_id(cat, IMPLEMENTING_ID)
    declared = [str(x) for x in (unit.get("tool_permissions") or []) if str(x).strip()]
    if not declared:
        raise RuntimeError(f"{IMPLEMENTING_ID} has empty tool_permissions")
    present = {rel: (REPO / rel).is_file() for rel in SOURCE_PATHS}
    return {
        "id": IMPLEMENTING_ID,
        "title": str(unit.get("title") or ""),
        "output_path": str(unit.get("output_path") or ""),
        "question_or_target": str(unit.get("question_or_target") or ""),
        "declared_permissions": declared,
        "tests_required": list(unit.get("tests_required") or []),
        "source_paths_present": present,
        "any_source_present": any(present.values()),
    }


def confirmer(catalog: dict | None = None) -> dict:
    cat = catalog if catalog is not None else load_catalog()
    unit = unit_by_id(cat, CONFIRMER_ID)
    return {
        "id": CONFIRMER_ID,
        "title": str(unit.get("title") or ""),
        "question_or_target": str(unit.get("question_or_target") or ""),
        "completion_sentinel": str(unit.get("completion_sentinel") or ""),
        "output_path": str(unit.get("output_path") or ""),
        "output_schema": str(unit.get("output_schema") or ""),
        "declared_permissions": [
            str(x) for x in (unit.get("tool_permissions") or []) if str(x).strip()
        ],
    }


def full_grant(declared: list[str]) -> list[str]:
    merged = list(dict.fromkeys([*declared, *SEED_DEFAULTS, *FULL_EXTRA]))
    return merged


def workunit_tool_permissions_field() -> dict:
    """Live inspect: does agentspec.WorkUnit carry tool_permissions yet?"""
    spec_path = REPO / "tools/agentspec/agentspec/spec.py"
    if not spec_path.is_file():
        return {
            "spec_present": False,
            "has_tool_permissions": False,
            "fields": [],
            "path": "tools/agentspec/agentspec/spec.py",
        }
    root = str(REPO / "tools/agentspec")
    if root not in sys.path:
        sys.path.insert(0, root)
    mod = importlib.import_module("agentspec.spec")
    fields = [f.name for f in dataclasses.fields(mod.WorkUnit)]
    return {
        "spec_present": True,
        "has_tool_permissions": "tool_permissions" in fields,
        "fields": fields,
        "path": "tools/agentspec/agentspec/spec.py",
    }
