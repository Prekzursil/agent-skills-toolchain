#!/usr/bin/env python3
"""Defaults-are-not-completeness validator for the Prompt Two work-unit schema.

Canonical field names are the 19 Prompt Two fields. A catalogue-level
`defaults` block does NOT satisfy completeness: a mandatory field present
only there is a violation. Completeness is armed with no disarm flag.

Scope: catalog['items'] (the 103-item Prompt Two estate that validate.py
V-FIELDS inspects). work_units are used only to derive closed enumerations.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CC_TOOLS = REPO / "tools" / "command-center"
if str(CC_TOOLS) not in sys.path:
    sys.path.insert(0, str(CC_TOOLS))

import catalog as cat  # noqa: E402

WORK_UNIT_FIELDS: tuple[str, ...] = tuple(cat.WORK_UNIT_FIELDS)
EMPTY_OK = frozenset({"inputs", "dependencies"})
KEBAB = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
FAILURE_ENUM_MIN_FREQ = 5
HISTORICAL_NINE: tuple[str, ...] = (
    "assignment",
    "tool_permissions",
    "execution_substrate",
    "timeout_seconds",
    "output_schema",
    "tests_required",
    "reviewer_requirement",
    "retry_policy",
    "failure_classification",
)
DEFAULT_SUBSTRATES: tuple[str, ...] = (
    "local-windows-pwsh7",
    "local-parallel",
    "local-serialized",
    "worktree-isolated",
    "cloud-batch",
)
DEFAULT_FAILURE_SIX: tuple[str, ...] = (
    "green-not-live",
    "overclaim",
    "detector-failure",
    "uncontrolled-silence",
    "dependency-blocked",
    "owner-blocked",
)
CONTRACT_REL = "command-center/phase4/contracts/ARC-0083.json"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"


def per_unit_present(item: dict[str, Any], field: str) -> bool:
    """True only when the item itself carries a resolved value (not defaults)."""
    if field not in item:
        return False
    value = item[field]
    if value is None:
        return False
    if isinstance(value, str):
        text = value.strip()
        return bool(text) and not text.startswith("UNKNOWN")
    if isinstance(value, (list, dict)):
        if field in EMPTY_OK:
            return True
        return bool(value)
    return True


def analyze(catalog: dict[str, Any]) -> dict[str, Any]:
    items = cat.items(catalog)
    defaults = (
        catalog.get("defaults", {})
        if isinstance(catalog.get("defaults"), dict)
        else {}
    )
    if not items:
        return {
            "items": 0,
            "defaults_only_counts": {},
            "unresolved_counts": {},
            "defaults_only_fields": [],
            "unresolved_fields": [],
            "violations": [
                {
                    "check": "V-EMPTY",
                    "field": "-",
                    "detail": "catalog holds zero items (fail closed)",
                }
            ],
        }

    defaults_only_counts: dict[str, int] = {}
    unresolved_counts: dict[str, int] = {}
    for field in WORK_UNIT_FIELDS:
        def_only = 0
        unresolved = 0
        for item in items:
            if per_unit_present(item, field):
                continue
            if field in EMPTY_OK:
                continue
            if field in defaults:
                def_only += 1
            else:
                unresolved += 1
        if def_only:
            defaults_only_counts[field] = def_only
        if unresolved:
            unresolved_counts[field] = unresolved

    n = len(items)
    violations: list[dict[str, Any]] = []
    for field, count in defaults_only_counts.items():
        violations.append(
            {
                "check": "V-DEFAULTS-ONLY",
                "field": field,
                "detail": (
                    f"present on {n - count}/{n} items; supplied only by "
                    f"catalogue defaults for {count}/{n}"
                ),
            }
        )
    for field, count in unresolved_counts.items():
        violations.append(
            {
                "check": "V-UNRESOLVED",
                "field": field,
                "detail": (
                    f"missing on {count}/{n} items and not in catalogue defaults"
                ),
            }
        )
    return {
        "items": n,
        "defaults_only_counts": defaults_only_counts,
        "unresolved_counts": unresolved_counts,
        "defaults_only_fields": sorted(defaults_only_counts),
        "unresolved_fields": sorted(unresolved_counts),
        "violations": violations,
    }


def expand_per_unit(catalog: dict[str, Any]) -> dict[str, Any]:
    """Copy catalogue defaults onto each item that lacks the field."""
    out = copy.deepcopy(catalog)
    defaults = (
        out.get("defaults", {}) if isinstance(out.get("defaults"), dict) else {}
    )
    for item in cat.items(out):
        if not isinstance(item, dict):
            continue
        for field in WORK_UNIT_FIELDS:
            if per_unit_present(item, field):
                continue
            if field in defaults:
                item[field] = copy.deepcopy(defaults[field])
    return out


def derive_substrate_enum(catalog: dict[str, Any]) -> list[str]:
    vals: set[str] = set(DEFAULT_SUBSTRATES)
    defaults = catalog.get("defaults") if isinstance(catalog.get("defaults"), dict) else {}
    raw = (defaults or {}).get("execution_substrate")
    if raw:
        vals.add(str(raw))
    for unit in catalog.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("execution_substrate"):
            vals.add(str(unit["execution_substrate"]))
    return sorted(vals)


def derive_failure_enum(catalog: dict[str, Any]) -> list[str]:
    counts: Counter[str] = Counter()
    for unit in catalog.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        raw = unit.get("failure_classification")
        values = raw if isinstance(raw, list) else [raw]
        for token in values:
            if token is None:
                continue
            text = str(token)
            if KEBAB.match(text):
                counts[text] += 1
    vals = {tok for tok, n in counts.items() if n >= FAILURE_ENUM_MIN_FREQ}
    vals.update(DEFAULT_FAILURE_SIX)
    defaults = catalog.get("defaults") if isinstance(catalog.get("defaults"), dict) else {}
    for token in (defaults or {}).get("failure_classification") or []:
        vals.add(str(token))
    return sorted(vals)


def build_schema(catalog: dict[str, Any]) -> dict[str, Any]:
    substrates = derive_substrate_enum(catalog)
    failures = derive_failure_enum(catalog)
    assignment = {
        "type": "object",
        "required": ["model", "vendor", "role"],
        "additionalProperties": True,
        "properties": {
            "model": {"type": "string", "minLength": 1},
            "vendor": {"type": "string", "minLength": 1},
            "role": {"type": "string", "minLength": 1},
            "basis": {"type": "string"},
        },
    }
    string_list = {
        "type": "array",
        "minItems": 1,
        "items": {"type": "string", "minLength": 1},
    }
    empty_ok_list = {
        "type": "array",
        "items": {"type": "string", "minLength": 1},
    }
    properties: dict[str, Any] = {
        "id": {
            "type": "string",
            "minLength": 3,
            "pattern": r"^(?:[A-Z]{2,5}-\d{4}|(?:R|D|S|T)-[A-Z]?\d+)$",
        },
        "title": {"type": "string", "minLength": 1},
        "phase": {"type": "string", "minLength": 1},
        "target": {"type": "string", "minLength": 1},
        "inputs": empty_ok_list,
        "dependencies": empty_ok_list,
        "assignment": assignment,
        "tool_permissions": string_list,
        "execution_substrate": {"type": "string", "enum": substrates},
        "timeout_seconds": {"type": "integer", "minimum": 1},
        "output_path": {"type": "string", "minLength": 1},
        "output_schema": {"type": "string", "minLength": 1},
        "evidence_requirement": {"type": "string", "minLength": 1},
        "tests_required": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 1},
        },
        "reviewer_requirement": {"type": "string", "minLength": 1},
        "completion_sentinel": {"type": "string", "minLength": 1},
        "retry_policy": {"type": "string", "minLength": 1},
        "failure_classification": {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {"type": "string", "enum": failures},
        },
        "owner_approval_required": {"type": "boolean"},
    }
    return {
        "type": "object",
        "additionalProperties": True,
        "required": list(WORK_UNIT_FIELDS),
        "properties": properties,
        "x-closed-enumerations": {
            "execution_substrate": substrates,
            "failure_classification": failures,
            "failure_classification_rule": (
                f"kebab-case tokens with frequency>={FAILURE_ENUM_MIN_FREQ} "
                "in work_units, union catalogue defaults"
            ),
        },
    }


def build_contract(catalog: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    schema = build_schema(catalog)
    extra = sorted(
        set(report["defaults_only_fields"]) - set(HISTORICAL_NINE)
    )
    historical_ok = all(
        field in report["defaults_only_fields"] for field in HISTORICAL_NINE
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": CONTRACT_REL,
        "$comment": (
            "SUCCESS:ARC-0083 canonical work-unit schema; defaults are not "
            "completeness; completeness check armed by default."
        ),
        "title": (
            "Work-unit schema with per-unit mandatory fields and a "
            "defaults-are-not-completeness validator"
        ),
        "description": (
            "JSON Schema (draft 2020-12) for the 19 Prompt Two work-unit fields "
            "(_USER-PROMPTS.md:10607-10625; catalog.contract.work_unit_fields). "
            "execution_substrate and failure_classification are closed enumerations. "
            "A mandatory field supplied only in catalogue defaults is incomplete. "
            "SUCCESS:ARC-0083"
        ),
        "unit_id": "ARC-0083",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0083",
        "completeness_validator": {
            "rule": "defaults-are-not-completeness",
            "armed_by_default": True,
            "disarm_flag": None,
            "catalog_collection": "items",
            "fail_on_defaults_only": True,
            "fail_on_unresolved": True,
            "fail_closed_empty_catalog": True,
            "reference_implementation": (
                "command-center/p2-wave/probes/ARC-0083/completeness.py"
            ),
            "historical_nine_defaults_only_fields": list(HISTORICAL_NINE),
        },
        "measured": {
            "catalog": CATALOG_REL,
            "items": report["items"],
            "defaults_only_fields": report["defaults_only_fields"],
            "defaults_only_counts": report["defaults_only_counts"],
            "unresolved_fields": report["unresolved_fields"],
            "historical_nine_all_reported": historical_ok,
            "live_vs_historical_extra": extra,
            "execution_substrate_enum": schema["x-closed-enumerations"][
                "execution_substrate"
            ],
            "failure_classification_enum_size": len(
                schema["x-closed-enumerations"]["failure_classification"]
            ),
            "work_unit_alias_drift": {
                "target": (
                    "work_units use question_or_target; canonical Prompt Two "
                    "field is target"
                ),
                "assignment": (
                    "work_units use assigned_model_vendor_role; canonical "
                    "Prompt Two field is assignment"
                ),
            },
        },
        "type": schema["type"],
        "additionalProperties": schema["additionalProperties"],
        "required": schema["required"],
        "properties": schema["properties"],
        "x-closed-enumerations": schema["x-closed-enumerations"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Work-unit completeness validator. Completeness is always on. "
            "Catalogue defaults do not count as per-unit fields."
        )
    )
    parser.add_argument(
        "--catalog",
        default=str(cat.catalog_path()),
        help="path to WORK-UNIT-CATALOG.json",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the machine-readable report",
    )
    args = parser.parse_args(argv)

    try:
        catalog = cat.load(args.catalog)
    except Exception as exc:
        print(f"FAILED:ARC-0083-completeness cannot read {args.catalog}: {exc}")
        return 1

    report = analyze(catalog)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for row in report["violations"]:
            print(f"  {row['check']} {row['field']}: {row['detail']}")
        print(
            "ARC-0083-completeness "
            f"items={report['items']} "
            f"defaults_only_fields={len(report['defaults_only_fields'])} "
            f"unresolved_fields={len(report['unresolved_fields'])}"
        )
    if report["violations"]:
        print(
            "FAILED:ARC-0083-completeness "
            f"violations={len(report['violations'])} "
            f"defaults_only_fields={len(report['defaults_only_fields'])} "
            f"unresolved_fields={len(report['unresolved_fields'])}"
        )
        return 1
    print(
        f"SUCCESS:ARC-0083-completeness items={report['items']} "
        "defaults_only_fields=0 unresolved_fields=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
