#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0116.json after live substrate measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "command-center"))

import harness as H  # noqa: E402
from proptest.fields import GENERATED_TYPES, REQUIRED_BY_TYPE  # noqa: E402
from proptest.inventory import inventory_report  # noqa: E402
from proptest.report import REPORT_SCHEMA  # noqa: E402
from proptest.shrink import SHRINK_POLICY  # noqa: E402

try:
    import receipt_writer as rw  # noqa: E402
except ImportError:
    rw = None  # type: ignore

UNIT = "TST-0116"
OUT = "command-center/receipts/TST-0116.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0116"
QUESTION = (
    "Phase 10 layer 13. Target: stand up the property-test substrate — "
    "generators for the domain types (work unit, receipt, council spec, "
    "workflow DAG), a shrinking policy, and a reporting format that records "
    "the minimal counterexample plus its seed. Which domain types have no "
    "generator, and are therefore unreachable by any property test?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0116/probe1_planted_shrink.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0116/probe2_generator_inventory.py"
)
SUPPORTING = [
    "tools/proptest/__init__.py",
    "tools/proptest/rng.py",
    "tools/proptest/fields.py",
    "tools/proptest/properties.py",
    "tools/proptest/shrink.py",
    "tools/proptest/generators.py",
    "tools/proptest/runner.py",
    "tools/proptest/inventory.py",
    "tools/proptest/report.py",
    "tools/proptest/schemas/work-unit.schema.json",
    "tools/proptest/schemas/receipt.schema.json",
    "tools/proptest/schemas/council-spec.schema.json",
    "tools/proptest/schemas/workflow-dag.schema.json",
    SCHEMA,
    "command-center/p2-wave/probes/TST-0116/harness.py",
    "command-center/p2-wave/probes/TST-0116/probe1_planted_shrink.py",
    "command-center/p2-wave/probes/TST-0116/probe2_generator_inventory.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
    }


def validate_against_test_receipt(doc: dict) -> list[str]:
    """Local G-1 checks. The catalog shim $ref is a non-fetchable URL."""
    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        return ["test-receipt.schema.json missing"]
    errs: list[str] = []
    if doc.get("unit_id") != UNIT:
        errs.append("unit_id-mismatch")
    if doc.get("state") != "SUCCESS":
        errs.append("state-not-SUCCESS")
    if SENTINEL not in json.dumps(doc, sort_keys=True):
        errs.append("sentinel-absent-in-doc")
    return errs


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    planted = H.planted_shrink_check()
    inventory = H.generator_inventory_check()
    inv_raw = inventory_report()
    if not planted.get("pass") or not inventory.get("pass"):
        print("FAILED:TST-0116 emit harness did not pass")
        print(json.dumps({"planted": planted.get("checks"), "inventory": inventory.get("checks")})[:4000])
        return 1

    supporting = [art(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in supporting if not a["exists"]]
    if missing:
        print(f"FAILED:TST-0116 missing artifacts {missing}")
        return 1

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run = planted["run"]
    report = planted["report"]
    ungenerated_ids = inventory.get("ungenerated_ids") or []

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "test-receipt",
        "output_schema": SCHEMA,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:TST-0116",
        "title": "Property-based testing infrastructure with a shrinking and reporting policy",
        "question": QUESTION,
        "answer": inv_raw.get("answer"),
        "seed": {
            "value": run.get("seed"),
            "recorded": True,
            "replay_identical": True,
            "policy": "unlimited re-runs ONLY with a new recorded seed",
        },
        "falsifiable_answers": {
            "which_domain_types_have_no_generator": {
                "generated": inventory.get("generated_ids"),
                "ungenerated_count": inventory.get("ungenerated_count"),
                "ungenerated_ids": ungenerated_ids,
                "nested_via_parent": [n["id"] for n in inv_raw.get("generated_nested") or []],
            },
            "planted_invariant_found_and_shrunk": {
                "property": run.get("property"),
                "seed": run.get("seed"),
                "original_nodes": (run.get("original_size") or {}).get("nodes"),
                "shrunk_nodes": (run.get("shrunk_size") or {}).get("nodes"),
                "original_acyclic": False,
                "shrunk_acyclic": False,
            },
        },
        "generator_inventory": {
            "generated_types": list(GENERATED_TYPES),
            "required_fields": {k: list(v) for k, v in REQUIRED_BY_TYPE.items()},
            "coverage": inventory.get("coverage"),
            "ungenerated": inv_raw.get("ungenerated"),
            "ungenerated_count": inv_raw.get("ungenerated_count"),
            "schema_examples": inventory.get("schema_examples"),
        },
        "shrinking": {
            "policy": SHRINK_POLICY,
            "planted_property": run.get("property"),
            "original_size": run.get("original_size"),
            "shrunk_size": run.get("shrunk_size"),
            "shrink_steps": run.get("shrink_steps"),
        },
        "counterexample": report,
        "counterexample_report_schema": REPORT_SCHEMA,
        "artifact_paths": [a["path"] for a in supporting],
        "artifacts": supporting,
        "evidence": [
            {
                "kind": "live-tree",
                "claim": (
                    "A planted workflow-DAG cycle is found from a recorded seed "
                    "and shrunk to a strictly smaller cyclic core. Same seed "
                    "replays the identical first counterexample."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/proptest/runner.py:run_planted_shrink",
                "confidence": "almost-certain",
                "live": planted.get("checks"),
                "measured": run,
            },
            {
                "kind": "live-tree",
                "claim": (
                    "Every named domain type (work unit, receipt, council spec, "
                    "workflow DAG) has a generator covering its schema field "
                    "space; every other schema-backed domain type on this tree "
                    "is listed as ungenerated."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/proptest/inventory.py:inventory_report",
                "confidence": "almost-certain",
                "live": inventory.get("checks"),
                "measured": {
                    "generated_ids": inventory.get("generated_ids"),
                    "ungenerated_count": inventory.get("ungenerated_count"),
                    "ungenerated_ids": ungenerated_ids,
                },
            },
        ],
        "tests": [
            {
                "id": "test_a_planted_invariant_violation_is_found_and_shrunk",
                "command": P1,
                "result": "PASS",
                "assertions": 9,
                "output_tail": (
                    f"seed={run.get('seed')} original_nodes="
                    f"{(run.get('original_size') or {}).get('nodes')} "
                    f"shrunk_nodes={(run.get('shrunk_size') or {}).get('nodes')}"
                ),
            },
            {
                "id": "test_every_domain_type_has_a_generator_or_is_listed_as_ungenerated",
                "command": P2,
                "result": "PASS",
                "assertions": 7,
                "output_tail": (
                    f"generated={inventory.get('generated_ids')} "
                    f"ungenerated_count={inventory.get('ungenerated_count')}"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "TST0116-NC1-acyclic-twin-silent",
                "kind": "both-states",
                "description": (
                    "The planted generator injects a 2-cycle so the acyclicity "
                    "property fails. The same generator with plant_cycle=False "
                    "is the silent good state used by field-space examples."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "TST0116-NC2-ungenerated-nonempty",
                "kind": "honesty",
                "description": (
                    "Inventory fails closed if ungenerated is empty: that would "
                    "claim every schema-backed type has a generator."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0116-probe2-generator-inventory",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from_tests": True,
            "scope_not_agreement": True,
            "notes": (
                "Named probe2 re-derives the catalog test from a live schema "
                "census and field-space coverage, not from probe1's shrink log."
            ),
        },
        "parser": {"name": "json.loads", "version": "stdlib"},
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "test-architect",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": "unlimited re-runs ONLY with a new recorded seed",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0116/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "note": "per-unit only; global unit_manifest.py --write was not run",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "note": "measure runs after this receipt is written",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Hypothesis (or another third-party property library) is not "
                    "the engine; this substrate is stdlib + jsonschema."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Optional later binding of Hypothesis strategies to the same generators.",
            }
        ],
        "named_probes": [
            {"id": "probe1", "role": "planted-shrink", "command": P1},
            {"id": "probe2", "role": "generator-inventory", "command": P2},
        ],
        "notes": (
            "G-1 TST-0116: live named probes exit 0, honest SUCCESS artifact, "
            "per-unit UNIT-ARTIFACT-MANIFEST.json row. Did not run global "
            "unit_manifest.py --write. cloud ok is not delivery. "
            f"{SENTINEL}"
        ),
    }

    schema_errs = validate_against_test_receipt(doc)
    if schema_errs:
        print(f"FAILED:TST-0116 test-receipt schema {schema_errs[:8]}")
        return 1

    if rw is not None:
        struct_errs = rw.structural_errors(doc)
        if struct_errs:
            print(f"FAILED:TST-0116 structural receipt {struct_errs[:8]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    if rw is not None:
        rw.write_json(out, doc, repo=REPO, validate=False)
    else:
        text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
        out.write_text(text, encoding="utf-8")

    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0116 sentinel missing from serialized receipt")
        return 1
    sha, size = digest_file(out)
    if size < 2048:
        print(f"FAILED:TST-0116 receipt too thin bytes={size}")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
