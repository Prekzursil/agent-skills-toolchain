"""CLI: validate the real catalog, the DSL examples, and the whole contract.

Usage (from the repo root)::

    python platform/lib/wfdsl/validate.py catalog command-center/WORK-UNIT-CATALOG.json
    python platform/lib/wfdsl/validate.py workflow platform/lib/wfdsl/examples/wf-full-coverage.json
    python platform/lib/wfdsl/validate.py all --json platform/schema/WORKFLOW-DSL-VALIDATION.json

Exit codes: ``0`` everything asserted held; ``1`` a contract assertion failed; ``2`` bad usage.
A non-zero exit from ``catalog`` on the ``normative``/``strict`` profiles is EXPECTED against the
current corpus - those profiles are stricter than the corpus on purpose - so ``all`` treats the
catalog profiles as MEASUREMENTS and gates only on the assertions that must hold today
(metaschema validity, 19-field structural conformance, capability coverage, mutation battery).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # allow `python platform/lib/wfdsl/validate.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from wfdsl import capabilities, mutations, resolve, schemas, semantics  # type: ignore[no-redef]
    from wfdsl import expr as _expr  # type: ignore[no-redef]
else:
    from . import capabilities, mutations, resolve, schemas, semantics
    from . import expr as _expr

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG = REPO_ROOT / "command-center" / "WORK-UNIT-CATALOG.json"
EXAMPLES = Path(__file__).resolve().parent / "examples"

SPEC_STOPPING_EXPRESSIONS: list[str] = [
    "unique_ideas >= 100 AND completeness_score >= 0.90",
    "consensus >= 0.95 AND no_new_objection_rounds >= 2",
    "unanimity == true OR max_rounds == 12",
    "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0",
    "evidence_saturation == true OR time_minutes >= 180",
    "proof_of_impossibility == true",
]

SPEC_STOPPING_CONTEXT: dict[str, Any] = {
    "unique_ideas": 104,
    "completeness_score": 0.93,
    "consensus": 0.97,
    "no_new_objection_rounds": 3,
    "unanimity": True,
    "max_rounds": 12,
    "quality_gate": "PASS",
    "unresolved_load_bearing_counterexample": 0,
    "evidence_saturation": True,
    "time_minutes": 42,
    "proof_of_impossibility": True,
}


# --------------------------------------------------------------------------- catalog


def validate_catalog(path: Path, profiles: tuple[str, ...] = ("structural", "normative", "strict")) -> dict[str, Any]:
    catalog = schemas.load_json(path)
    units = catalog.get("work_units") or []

    container_errors = schemas.error_summary(schemas.catalog_validator().iter_errors(catalog), limit=8)

    out: dict[str, Any] = {
        "catalog": str(path),
        "work_units": len(units),
        "container_schema_errors": container_errors,
        "container_valid": not container_errors,
        "profiles": {},
        "defaults_audit": resolve.defaults_are_load_bearing(catalog),
        "missing_mandated_fields": {},
    }

    missing = Counter()
    for u in units:
        for f in resolve.missing_fields(u):
            missing[f] += 1
    out["missing_mandated_fields"] = dict(missing)

    for profile in profiles:
        validator = schemas.work_unit_validator(profile)
        failing: list[dict[str, Any]] = []
        failing_ids: list[str] = []
        reasons: Counter = Counter()
        for u in units:
            errs = sorted(validator.iter_errors(u), key=lambda e: list(e.absolute_path))
            if not errs:
                continue
            failing_ids.append(str(u.get("id")))
            keys = sorted({(("/".join(str(p) for p in e.absolute_path) or "<root>"), e.validator) for e in errs})
            for loc, kw in keys:
                reasons[f"{loc} [{kw}]"] += 1
            if len(failing) < 25:
                failing.append({"id": u.get("id"), "errors": schemas.error_summary(errs, limit=3)})
        out["profiles"][profile] = {
            "pass": len(units) - len(failing_ids),
            "fail": len(failing_ids),
            "reason_histogram": dict(reasons.most_common(20)),
            "sample_failures": failing[:15],
            "failing_ids_sample": failing_ids[:40],
            "_failing_ids": failing_ids,
        }

    # A strict failure that ALSO fails normative is a cascade: when the referenced normative
    # subschema fails, draft 2020-12 discards its annotations, so `unevaluatedProperties` fires
    # at <root> for reasons that have nothing to do with unknown properties. Separate the two
    # so the strict histogram is never read as 217 typo'd fields.
    if "strict" in out["profiles"] and "normative" in out["profiles"]:
        norm_fail = set(out["profiles"]["normative"]["_failing_ids"])
        strict_fail = set(out["profiles"]["strict"]["_failing_ids"])
        out["profiles"]["strict"]["cascade_from_normative"] = len(strict_fail & norm_fail)
        out["profiles"]["strict"]["strict_only"] = sorted(strict_fail - norm_fail)[:40]
        out["profiles"]["strict"]["strict_only_count"] = len(strict_fail - norm_fail)
    for prof in out["profiles"].values():
        prof.pop("_failing_ids", None)

    out["semantic_rules"] = [r.to_json() for r in semantics.check_work_units(units)]
    return out


# -------------------------------------------------------------------------- workflows


def validate_workflow(path: Path) -> dict[str, Any]:
    doc = schemas.load_json(path)
    errs = sorted(schemas.workflow_validator().iter_errors(doc), key=lambda e: list(e.absolute_path))
    sem = semantics.check_workflow(doc)
    return {
        "workflow": str(path),
        "id": doc.get("id"),
        "schema_valid": not errs,
        "schema_errors": schemas.error_summary(errs, limit=8),
        "semantic_rules": [r.to_json() for r in sem],
        "semantic_violations": sum(len(r.violations) for r in sem if r.severity == "violation"),
        "semantic_advisories": sum(len(r.violations) for r in sem if r.severity == "advisory"),
    }


def validate_examples() -> dict[str, Any]:
    rows = []
    for path in sorted(EXAMPLES.glob("wf-*.json")):
        rows.append(validate_workflow(path))
    return {"count": len(rows), "results": rows}


def check_spec_expressions() -> dict[str, Any]:
    rows = []
    for text in SPEC_STOPPING_EXPRESSIONS:
        row: dict[str, Any] = {"expression": text}
        try:
            ast = _expr.parse(text)
            row["parsed"] = True
            row["identifiers"] = sorted(ast.identifiers())
            row["evaluates_true_on_reference_context"] = bool(ast.evaluate(SPEC_STOPPING_CONTEXT))
        except _expr.ExpressionError as exc:
            row["parsed"] = False
            row["error"] = str(exc)
        rows.append(row)
    return {
        "count": len(rows),
        "parsed": sum(1 for r in rows if r.get("parsed")),
        "all_true_on_reference_context": all(r.get("evaluates_true_on_reference_context") for r in rows),
        "results": rows,
    }


# ------------------------------------------------------------------------------- all


def run_all(catalog_path: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "artifact": "platform/schema/WORKFLOW-DSL-VALIDATION.json",
        "unit": "contracts/workflow-dsl",
        "status": "MEASURED",
        "schema_dir": str(schemas.SCHEMA_DIR),
    }
    report["metaschema"] = schemas.check_metaschema()
    report["catalog"] = validate_catalog(catalog_path)
    report["examples"] = validate_examples()
    base = schemas.load_json(EXAMPLES / "wf-full-coverage.json")
    report["capability_coverage"] = capabilities.check_coverage()
    report["mutation_battery"] = mutations.run_battery(base)
    report["spec_stopping_expressions"] = check_spec_expressions()

    # the defaults-block properties, measured on purpose-built fixtures
    no_def = schemas.load_json(EXAMPLES / "catalog-no-defaults.json")
    lean = schemas.load_json(EXAMPLES / "catalog-defaults-only.json")
    cat_v = schemas.catalog_validator()
    unit_v = schemas.work_unit_validator("strict")
    struct_v = schemas.work_unit_validator("structural")
    lean_raw_fail = [u.get("id") for u in lean["work_units"] if list(struct_v.iter_errors(u))]
    resolved = [resolve.resolve_unit(u, lean.get("defaults")) for u in lean["work_units"]]
    lean_resolved_fail = [r.unit.get("id") for r in resolved if list(struct_v.iter_errors(r.unit))]
    report["defaults_block_semantics"] = {
        "catalog_without_defaults_validates": not list(cat_v.iter_errors(no_def)),
        "its_unit_passes_strict_profile": not list(unit_v.iter_errors(no_def["work_units"][0])),
        "lean_catalog_units_failing_raw": lean_raw_fail,
        "lean_catalog_units_failing_after_resolution": lean_resolved_fail,
        "resolver_filled": {r.unit.get("id"): r.filled for r in resolved},
        "resolver_refused": {r.unit.get("id"): r.refused for r in resolved},
    }

    # gating assertions: what MUST hold right now
    cat = report["catalog"]
    cov = report["capability_coverage"]
    bat = report["mutation_battery"]
    dbs = report["defaults_block_semantics"]
    examples_ok = all(r["schema_valid"] and r["semantic_violations"] == 0 for r in report["examples"]["results"])
    assertions = {
        "every schema validates against the draft 2020-12 metaschema": len(report["metaschema"]) == len(schemas.SCHEMA_FILES),
        "catalog container validates": cat["container_valid"],
        "no catalog unit is missing a mandated field": not cat["missing_mandated_fields"],
        "all catalog units pass the structural profile": cat["profiles"]["structural"]["fail"] == 0,
        "defaults block is not load-bearing in the real catalog": not cat["defaults_audit"]["load_bearing"],
        "a catalog with NO defaults block validates": dbs["catalog_without_defaults_validates"],
        "the strict profile is satisfiable by a real unit": dbs["its_unit_passes_strict_profile"],
        "a defaults-leaning unit is rejected raw": "WU-0001" in dbs["lean_catalog_units_failing_raw"],
        "the resolver completes it in resolved mode": "WU-0001" not in dbs["lean_catalog_units_failing_after_resolution"],
        "the resolver refuses to default output_path": dbs["resolver_refused"].get("WU-0002") == ["output_path"],
        "every DSL example is schema-valid with zero semantic violations": examples_ok,
        "every mandated capability is covered": cov["mandated"] == cov["mandated_covered"],
        "every mutation is caught by its declared layer": bat["caught_by_declared_layer"] == bat["mutations"],
        "no mutation survives": not bat["survivors"],
        "all six spec stopping expressions parse and evaluate true on the reference context": report["spec_stopping_expressions"]["parsed"] == 6
        and report["spec_stopping_expressions"]["all_true_on_reference_context"],
    }
    report["assertions"] = assertions
    report["assertions_failed"] = sorted(k for k, v in assertions.items() if not v)
    report["ok"] = not report["assertions_failed"]
    return report


def _print_summary(report: dict[str, Any]) -> None:
    cat = report["catalog"]
    print(f"catalog            : {cat['catalog']}")
    print(f"work units         : {cat['work_units']}")
    for name, prof in cat["profiles"].items():
        print(f"  profile {name:<11}: pass={prof['pass']:>5} fail={prof['fail']:>5}")
        for reason, count in list(prof["reason_histogram"].items())[:6]:
            print(f"      {count:>5} x {reason}")
    print("semantic rules (work units):")
    for r in cat["semantic_rules"]:
        print(f"  {r['rule']} {r['severity']:<9} violations={r['violations']:<5} {r['description'][:78]}")
    cov = report["capability_coverage"]
    print(f"capabilities       : {cov['mandated_covered']}/{cov['mandated']} mandated covered, {cov['all_covered']}/{cov['capabilities']} total")
    for row in cov["uncovered"]:
        print(f"  UNCOVERED {row['id']}: {row['gaps']}")
    bat = report["mutation_battery"]
    print(f"mutation battery   : {bat['caught_by_declared_layer']}/{bat['mutations']} caught by declared layer; survivors={bat['survivors']}")
    print(f"spec expressions   : {report['spec_stopping_expressions']['parsed']}/6 parsed")
    print(f"examples           : {report['examples']['count']} validated")
    for k, v in report["assertions"].items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print("RESULT:", "SUCCESS:contracts/workflow-dsl" if report["ok"] else "FAILED:contracts/workflow-dsl " + ", ".join(report["assertions_failed"]))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="wfdsl.validate", description="Workflow DSL / work-unit contract validator")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_cat = sub.add_parser("catalog", help="validate a work-unit catalog")
    p_cat.add_argument("path", nargs="?", default=str(DEFAULT_CATALOG))
    p_cat.add_argument("--profile", action="append", choices=sorted(schemas.WORK_UNIT_PROFILES))
    p_cat.add_argument("--json")

    p_wf = sub.add_parser("workflow", help="validate one or more workflow documents")
    p_wf.add_argument("paths", nargs="+")
    p_wf.add_argument("--json")

    p_all = sub.add_parser("all", help="run every contract check and emit the validation artifact")
    p_all.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    p_all.add_argument("--json")

    args = ap.parse_args(argv)

    if args.cmd == "catalog":
        profiles = tuple(args.profile) if args.profile else ("structural", "normative", "strict")
        report = validate_catalog(Path(args.path), profiles)
        if args.json:
            Path(args.json).write_text(json.dumps(report, indent=1), encoding="utf-8")
        print(json.dumps({k: v for k, v in report.items() if k != "semantic_rules"}, indent=1)[:4000])
        for r in report["semantic_rules"]:
            print(f"{r['rule']} {r['severity']:<9} violations={r['violations']:<5} {r['description'][:80]}")
        return 0 if report["container_valid"] and report["profiles"].get("structural", {}).get("fail", 1) == 0 else 1

    if args.cmd == "workflow":
        rows = [validate_workflow(Path(p)) for p in args.paths]
        if args.json:
            Path(args.json).write_text(json.dumps(rows, indent=1), encoding="utf-8")
        print(json.dumps(rows, indent=1)[:6000])
        return 0 if all(r["schema_valid"] and r["semantic_violations"] == 0 for r in rows) else 1

    report = run_all(Path(args.catalog))
    target = Path(args.json) if args.json else schemas.SCHEMA_DIR / "WORKFLOW-DSL-VALIDATION.json"
    target.write_text(json.dumps(report, indent=1), encoding="utf-8")
    _print_summary(report)
    print(f"(artifact written: {target})")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
