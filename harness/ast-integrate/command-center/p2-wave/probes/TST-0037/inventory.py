"""Live production inventory for the seven documented workflow-DSL constructs."""
from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path
from typing import Any

from constructs import BY_ID, CONSTRUCTS, ORDER

AGENTSPEC = Path("tools/agentspec")

# Production node classes → closed-type tokens. Aliases such as "loop" are
# excluded from test-corpus needles because they are substrings of
# "repair-loop" and would false-hit IMP-0139 coverage.
CLASS_TO_CLOSED = {
    "FanOut": "fanout",
    "Barrier": "barrier",
    "Pipeline": "pipeline",
    "RepairLoop": "repair-loop",
    "Loop": "loop-with-convergence",
    "HumanCheckpoint": "human-checkpoint",
    "Subworkflow": "subworkflow",
    "Retry": "retry",
    "Resume": "resume",
}
SUBSTRING_UNSAFE = frozenset({"loop", "checkpoint", "fan-out"})


def _read(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _class_names(source: str) -> set[str]:
    if not source.strip():
        return set()
    tree = ast.parse(source)
    return {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}


def _load_validate(repo: Path):
    root = repo / AGENTSPEC
    path = str(root)
    if path not in sys.path:
        sys.path.insert(0, path)
    import agentspec.validate as validate

    return importlib.reload(validate)


def _load_closure(repo: Path):
    root = repo / AGENTSPEC
    path = str(root)
    if path not in sys.path:
        sys.path.insert(0, path)
    import agentspec.id_closure as closure

    return importlib.reload(closure)


def _test_corpus(repo: Path) -> str:
    tests = repo / AGENTSPEC / "tests"
    chunks: list[str] = []
    if tests.is_dir():
        for path in sorted(tests.glob("test_*.py")):
            chunks.append(_read(path))
    return "\n".join(chunks)


def scan(repo: Path) -> dict[str, Any]:
    spec_path = repo / AGENTSPEC / "agentspec" / "spec.py"
    validate_path = repo / AGENTSPEC / "agentspec" / "validate.py"
    tests_text = _test_corpus(repo)
    spec_classes = _class_names(_read(spec_path))
    closed: set[str] = {
        CLASS_TO_CLOSED[name] for name in spec_classes if name in CLASS_TO_CLOSED
    }
    emitted: set[str] = set()
    documented: set[str] = set()
    validate_present = validate_path.is_file()
    import_error = None
    if validate_present:
        try:
            validate = _load_validate(repo)
            named = getattr(validate, "CLOSED_NODE_TYPES", None)
            if named:
                closed |= {str(x) for x in named}
            violations = getattr(validate, "VIOLATIONS", ()) or ()
            emitted |= {str(x) for x in violations}
            closure = _load_closure(repo)
            emitted |= set(closure.extract_emitted_ids(_read(validate_path)))
            documented = set(closure.documented_ids())
        except Exception as exc:  # pragma: no cover - sibling write races
            import_error = f"{type(exc).__name__}: {exc}"

    rows = []
    for spec in CONSTRUCTS:
        cid = spec["id"]
        prod_types = set(spec["production_types"])
        in_closed = sorted(prod_types & closed)
        schema_ids = sorted(set(spec["violation_ids"]) & emitted & documented)
        has_schema_rule = bool(in_closed) or bool(schema_ids)
        needles = (set(spec["violation_ids"]) | {cid} | prod_types) - SUBSTRING_UNSAFE
        test_hits = [needle for needle in sorted(needles) if needle and needle in tests_text]
        has_prod_case = bool(test_hits)
        spec_hits = sorted(set(spec["spec_classes"]) & spec_classes)
        has_validator = bool(in_closed)
        rows.append(
            {
                "construct": cid,
                "schema_rule": has_schema_rule,
                "schema_rule_ids": schema_ids,
                "schema_rule_closed_types": in_closed,
                "conformance_case_production": has_prod_case,
                "production_test_hits": test_hits,
                "production_validator": has_validator,
                "spec_classes_present": spec_hits,
                "not_this": spec.get("not_this"),
            }
        )

    missing_validator = [r["construct"] for r in rows if not r["production_validator"]]
    missing_schema = [r["construct"] for r in rows if not r["schema_rule"]]
    missing_prod_case = [r["construct"] for r in rows if not r["conformance_case_production"]]
    every_prod = all(
        r["schema_rule"] and r["conformance_case_production"] and r["production_validator"]
        for r in rows
    )
    return {
        "validate_present": validate_present,
        "import_error": import_error,
        "closed_node_types": sorted(closed),
        "spec_classes": sorted(spec_classes),
        "emitted_violation_ids": sorted(emitted),
        "documented_violation_ids": sorted(documented),
        "rows": rows,
        "order": list(ORDER),
        "every_construct_has_production_schema_rule_and_conformance_case": (
            all(r["schema_rule"] and r["conformance_case_production"] for r in rows)
        ),
        "every_construct_has_production_validator": all(r["production_validator"] for r in rows),
        "constructs_with_no_production_validator": missing_validator,
        "constructs_with_no_production_schema_rule": missing_schema,
        "constructs_with_no_production_conformance_case": missing_prod_case,
        "every_construct_fully_covered_in_production": every_prod,
        "paths": {
            "spec": "tools/agentspec/agentspec/spec.py",
            "validate": "tools/agentspec/agentspec/validate.py",
            "violation_ids": "tools/agentspec/docs/violation-ids.json",
            "tests": "tools/agentspec/tests/test_validate.py",
        },
    }


def row_for(inventory: dict, construct_id: str) -> dict:
    for row in inventory.get("rows") or []:
        if row.get("construct") == construct_id:
            return row
    return dict(BY_ID[construct_id])
