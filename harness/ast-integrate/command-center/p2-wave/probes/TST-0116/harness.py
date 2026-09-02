"""Live checks for TST-0116 named probes. Does not write the catalog receipt."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from proptest.generators import coverage_for, field_space_examples  # noqa: E402
from proptest.inventory import inventory_report  # noqa: E402
from proptest.report import planted_report  # noqa: E402
from proptest.runner import run_planted_shrink  # noqa: E402
from proptest.shrink import SHRINK_POLICY  # noqa: E402

SCHEMA_DIR = REPO / "tools" / "proptest" / "schemas"
SCHEMA_FILES = {
    "work_unit": SCHEMA_DIR / "work-unit.schema.json",
    "receipt": SCHEMA_DIR / "receipt.schema.json",
    "council_spec": SCHEMA_DIR / "council-spec.schema.json",
    "workflow_dag": SCHEMA_DIR / "workflow-dag.schema.json",
}


def _validate_examples() -> dict[str, Any]:
    try:
        import jsonschema
    except ImportError:
        return {"pass": False, "reason": "jsonschema-missing"}
    rows = []
    ok = True
    for kind, path in SCHEMA_FILES.items():
        schema = json.loads(path.read_text(encoding="utf-8"))
        validator = jsonschema.Draft7Validator(schema)
        examples = field_space_examples(kind)
        errors = 0
        for ex in examples:
            errors += sum(1 for _ in validator.iter_errors(ex))
        cov = coverage_for(kind)
        row = {
            "type": kind,
            "schema": path.relative_to(REPO).as_posix(),
            "examples": len(examples),
            "schema_errors": errors,
            "coverage_pass": cov.get("pass"),
            "missing_fields": cov.get("missing_fields"),
        }
        if errors or not cov.get("pass"):
            ok = False
        rows.append(row)
    return {"pass": ok, "rows": rows}


def planted_shrink_check() -> dict[str, Any]:
    packed = planted_report()
    run = packed["run"]
    report = packed["report"]
    ok = bool(run.get("pass")) and report.get("verdict") == "FAIL"
    orig = run.get("original_size") or {}
    shrunk = run.get("shrunk_size") or {}
    checks = {
        "found": run.get("trial_index") is not None,
        "original_fails": run.get("original_acyclic") is False,
        "shrunk_fails": run.get("shrunk_acyclic") is False,
        "shrunk_smaller": (
            isinstance(orig, dict)
            and isinstance(shrunk, dict)
            and (shrunk.get("nodes"), shrunk.get("edges"), shrunk.get("bytes"))
            < (orig.get("nodes"), orig.get("edges"), orig.get("bytes"))
        ),
        "original_nodes_ge_8": (orig.get("nodes") or 0) >= 8,
        "shrunk_nodes_ge_2": (shrunk.get("nodes") or 0) >= 2,
        "replay_identical": bool(run.get("replay_identical")),
        "shrink_deterministic": bool(run.get("shrink_deterministic")),
        "seed_recorded": run.get("seed") is not None,
        "report_has_minimal_ce": isinstance(report.get("shrunk"), dict),
        "policy_name": SHRINK_POLICY.get("name"),
    }
    return {
        "pass": ok and all(
            v is True
            for k, v in checks.items()
            if k != "policy_name"
        ),
        "checks": checks,
        "run": {
            "seed": run.get("seed"),
            "trial_index": run.get("trial_index"),
            "original_size": orig,
            "shrunk_size": shrunk,
            "shrink_steps": run.get("shrink_steps"),
            "property": run.get("property"),
        },
        "report": report,
    }


def generator_inventory_check() -> dict[str, Any]:
    inv = inventory_report()
    schema_ok = _validate_examples()
    generated_ids = [g["id"] for g in inv.get("generated") or []]
    want = ["work_unit", "receipt", "council_spec", "workflow_dag"]
    checks = {
        "four_generated": generated_ids == want,
        "coverage_ok": bool(inv.get("coverage_ok")),
        "ungenerated_nonempty": (inv.get("ungenerated_count") or 0) > 0,
        "no_overlap": not inv.get("overlap"),
        "no_missing_named": not inv.get("missing_named"),
        "schema_examples_valid": bool(schema_ok.get("pass")),
        "inventory_pass": bool(inv.get("pass")),
    }
    return {
        "pass": all(checks.values()) and bool(inv.get("pass")),
        "checks": checks,
        "generated_ids": generated_ids,
        "ungenerated_count": inv.get("ungenerated_count"),
        "ungenerated_ids": inv.get("ungenerated_ids"),
        "answer": inv.get("answer"),
        "question": inv.get("question"),
        "schema_examples": schema_ok,
        "coverage": [g.get("coverage") for g in inv.get("generated") or []],
    }
