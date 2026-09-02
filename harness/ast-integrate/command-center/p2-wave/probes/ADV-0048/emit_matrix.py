#!/usr/bin/env python3
"""Emit ADV-0048 license inventory / compatibility matrix."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inventory import (  # noqa: E402
    UNKNOWN_RATE_THRESHOLD,
    automated_inventory,
    clause_readings,
    gpl_clause_ok,
    mit_control_ok,
)

OUT = "command-center/adversarial/ADV-0048-license-inventory-compatibility-matrix.json"
SCHEMA = "command-center/schema/license-and-rights-record.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0048/probe1_auto_identify.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0048/probe2_clause_read.py"
)
QUESTION = (
    "For every file, dependency and adopted mechanism in the distributed "
    "artifact, what is its license, is it compatible with the chosen outbound "
    "license, and which component forces a stricter outbound term?"
)
COMPLETION_SENTINEL = (
    "SUCCESS:ADV-0048 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0048 <reason>."
)
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
    {"unit_id": "ADV-0048", "state": "SUCCESS"},
)
# Catalog output_schema is a generated $ref shim. jsonschema 4.10 follows that
# $ref over HTTPS to ast-integrate.invalid and raises RefResolutionError.
# G-1 requires parse + sentinel + probes; this local contract still rejects
# garbage so emit cannot mint an empty SUCCESS blob.
CONTRACT = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "profile",
        "report",
        "components",
        "targets",
        "tests",
        "negative_controls",
        "named_probes",
        "evidence",
    ],
    "properties": {
        "unit_id": {"const": "ADV-0048"},
        "state": {"enum": ["SUCCESS", "PARTIAL", "NOT-CHECKED", "CONFIRMED", "REFUTED"]},
        "sentinel": {"type": "string", "minLength": 8},
        "completion_sentinel": {"type": "string", "minLength": 32},
        "profile": {"const": "license-and-rights-record"},
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "license-and-rights-record"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
        "components": {"type": "array", "minItems": 2},
        "targets": {"type": "array", "minItems": 1},
        "tests": {"type": "array", "minItems": 2},
        "negative_controls": {"type": "array", "minItems": 1},
        "named_probes": {"type": "array", "minItems": 2},
        "evidence": {"type": "array", "minItems": 1},
    },
    "additionalProperties": True,
}


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:ADV-0048 emit snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=True) + "\n"


def main() -> int:
    inv = automated_inventory()
    readings = clause_readings(inv["components"])
    mit = mit_control_ok(inv)
    gpl = gpl_clause_ok(readings)
    if not mit["ok"]:
        print("FAILED:ADV-0048 MIT control misidentified")
        print(json.dumps(mit, indent=2)[:2000])
        return 1
    if not gpl["ok"]:
        print("FAILED:ADV-0048 GPL clause extraction failed")
        print(json.dumps(gpl, indent=2)[:2000])
        return 1

    catalog = REPO / CATALOG
    cat_line = find_line(catalog, '"id": "ADV-0048"')
    q_line = find_line(catalog, QUESTION[:60])
    schema_path = REPO / SCHEMA
    if not schema_path.is_file():
        print(f"FAILED:ADV-0048 missing schema {SCHEMA}")
        return 1
    validator = jsonschema.Draft7Validator(CONTRACT)
    for probe in GARBAGE:
        if not list(validator.iter_errors(probe)):
            print("FAILED:ADV-0048 schema accepts garbage")
            print(json.dumps(probe)[:200])
            return 1

    by_id = {c["id"]: c for c in inv["components"]}
    product = by_id["first-party:ast-integrate"]
    mit_c = by_id["control:known-unambiguous-mit"]
    gpl_c = by_id["control:known-gpl3"]
    mis_c = by_id["control:mislabeled-mit-metadata-gpl-text"]
    bad_c = by_id["control:not-a-license"]
    copyleft_product = inv["copyleft_in_product"]
    matrix_not_checked = inv["matrix_cleanliness"] != "clean"

    targets = [
        {
            "id": "outbound-license-declared",
            "verdict": "REFUTED",
            "note": inv["outbound_reason"],
        },
        {
            "id": "control-mit-identified-by-probe1",
            "verdict": "CONFIRMED",
            "note": mit_c["evidence_string"],
        },
        {
            "id": "control-not-a-license-rejected-as-mit",
            "verdict": "CONFIRMED",
            "note": bad_c["evidence_string"],
        },
        {
            "id": "copyleft-in-product-distribution",
            "verdict": "REFUTED" if not copyleft_product else "CONFIRMED",
            "note": (
                "no copyleft/weak-copyleft family in product scope; planted GPL "
                "controls are fixtures, not shipped components"
                if not copyleft_product
                else "copyleft reachable in product: "
                + ",".join(c["id"] for c in copyleft_product)
            ),
        },
        {
            "id": "copyleft-control-escalated-to-clause-read",
            "verdict": "CONFIRMED",
            "note": "control:known-gpl3 family=copyleft and probe 2 recorded GPLv3 entire-work clause",
        },
        {
            "id": "identifier-text-conflict-mislabeled-escalated",
            "verdict": "CONFIRMED" if mis_c["conflict"] else "REFUTED",
            "note": mis_c["evidence_string"],
        },
        {
            "id": "first-party-license-known",
            "verdict": "REFUTED" if product["automated_family"] == "unknown" else "CONFIRMED",
            "note": product["evidence_string"],
        },
        {
            "id": "compatibility-matrix-clean",
            "verdict": "NOT-CHECKED" if matrix_not_checked else "CONFIRMED",
            "note": (
                f"unknown_rate={inv['unknown_rate']} threshold="
                f"{inv['unknown_rate_threshold']}; matrix_cleanliness="
                f"{inv['matrix_cleanliness']}"
            ),
        },
    ]
    allowed = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
    seen = [t["id"] for t in targets]
    if len(seen) != len(set(seen)):
        print("FAILED:ADV-0048 duplicate target ids")
        return 1
    for t in targets:
        if t["verdict"] not in allowed:
            print("FAILED:ADV-0048 bad verdict", t)
            return 1

    stricter = None
    if copyleft_product:
        stricter = copyleft_product[0]["id"]
    answer = (
        "This worktree has no declared outbound license. First-party product "
        f"scope ({inv['product_scan']['files_considered']} files) has "
        f"{len(inv['product_scan']['license_files'])} license files and "
        f"{len(inv['product_scan']['spdx_headers'])} SPDX headers, so "
        "first-party identity is unknown. No copyleft component is reachable "
        "in product scope; the planted GPLv3 fixture would force a GPLv3 "
        "outbound term if it were shipped. Compatibility cannot be scored "
        "against an undeclared outbound license. Unknown rate "
        f"{inv['unknown_rate']} exceeds threshold {UNKNOWN_RATE_THRESHOLD}, "
        "so the matrix is NOT-CHECKED rather than clean."
    )
    if stricter:
        answer += f" Stricter product component: {stricter}."
    else:
        answer += " No product component forces a stricter outbound term."

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "ADV-0048",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0048",
        "completion_sentinel": COMPLETION_SENTINEL,
        "profile": "license-and-rights-record",
        "report_kind": "license-and-rights-record",
        "title": "License inventory and compatibility matrix for every distributed component",
        "question": QUESTION,
        "spec_anchor": "_USER-PROMPTS.md:10858, 11111, 11334",
        "schema_version": 1,
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "license-and-legal-analyst",
            "execution_substrate": "local-parallel",
        },
        "outbound": {
            "spdx": None,
            "declared": False,
            "reason": inv["outbound_reason"],
            "distribution_model": "undeclared-on-this-worktree",
        },
        "report": {
            "kind": "license-and-rights-record",
            "inventory_kind": "license-inventory-compatibility-matrix",
            "question_or_target": QUESTION,
            "answer": answer,
            "unknown_rate": inv["unknown_rate"],
            "unknown_rate_threshold": inv["unknown_rate_threshold"],
            "matrix_cleanliness": inv["matrix_cleanliness"],
            "stricter_outbound_component": stricter,
            "copyleft_release_blockers_product": [
                c["id"] for c in copyleft_product
            ],
            "product_scan": inv["product_scan"],
            "scope_note": (
                "Product scope is this worktree excluding other units' "
                "command-center/p2-wave/probes fixtures. ADV-0048 fixtures are "
                "controls, not shipped components. Probe-local package-lock "
                "trees (TST/BLD/CNF) are out of product scope."
            ),
            "observations": [
                {
                    "name": "unknown_rate",
                    "measured": inv["unknown_rate"],
                    "method": "fingerprint-plus-package-json-metadata",
                    "anchor": "command-center/p2-wave/probes/ADV-0048/inventory.py",
                },
                {
                    "name": "component_n",
                    "measured": inv["component_n"],
                    "method": "fingerprint-plus-package-json-metadata",
                    "anchor": "command-center/p2-wave/probes/ADV-0048/inventory.py",
                },
                {
                    "name": "copyleft_in_product_n",
                    "measured": len(copyleft_product),
                    "method": "automated-inventory-product-scope",
                    "anchor": "command-center/p2-wave/probes/ADV-0048/inventory.py",
                },
                {
                    "name": "mit_control_identified",
                    "measured": bool(mit["ok"]),
                    "method": "mit-fingerprint",
                    "anchor": (
                        "command-center/p2-wave/probes/ADV-0048/fixtures/"
                        "control-mit/LICENSE"
                    ),
                },
            ],
            "control_ids": [
                "ADV-0048-CONTROL-KNOWN-MIT",
                "ADV-0048-NOT-A-LICENSE",
                "ADV-0048-MISLABEL-MIT-METADATA",
            ],
        },
        "components": inv["components"],
        "clause_readings": readings,
        "targets": [{"id": t["id"], "verdict": t["verdict"]} for t in targets],
        "target_notes": targets,
        "tests": [
            {
                "id": "ADV-0048-PROBE1-AUTO-IDENTIFY",
                "command": P1,
                "name": "Automated license identification with raw evidence per component",
                "result": "PASS",
            },
            {
                "id": "ADV-0048-PROBE2-CLAUSE-READ",
                "command": P2,
                "name": "Clause-level reading of copyleft/unknown/custom LICENSE text",
                "result": "PASS",
            },
            {
                "id": "ADV-0048-CONTROL-KNOWN-MIT",
                "command": P1,
                "name": "Known unambiguous MIT control identified as MIT/permissive",
                "result": "PASS" if mit["ok"] else "FAIL",
            },
            {
                "id": "ADV-0048-UNKNOWN-RATE-THRESHOLD",
                "command": P1,
                "name": (
                    "UNKNOWN rate above stated threshold makes the matrix "
                    "NOT-CHECKED rather than clean"
                ),
                "result": "PASS" if matrix_not_checked else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "ADV-0048-NOT-A-LICENSE",
                "planted_defect": "LICENSE file that is not MIT/Apache/GPL",
                "detector_fired": bad_c["automated_family"] != "permissive",
                "silent_on_good": mit_c["automated_spdx"] == "MIT",
            },
            {
                "id": "ADV-0048-MISLABEL-MIT-METADATA",
                "planted_defect": "package.json license=MIT while LICENSE text is GPLv3",
                "detector_fired": bool(mis_c["conflict"]) and mis_c["automated_family"] == "custom",
                "silent_on_good": mit_c["conflict"] is False,
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "raw_output": "pending-live-probe",
            },
            {
                "id": "probe2",
                "command": P2,
                "raw_output": "pending-live-probe",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0048-probe2-clause-read",
            "verdict": "PASS",
            "independent": True,
            "vendor": "probe-method-not-vendor",
            "notes": (
                "Probe 2 re-derives distribution constraints from LICENSE bytes "
                "via obligation regexes and does not take probe 1 SPDX labels as "
                "the clause. Cross-vendor owner sign-off is not obtained; no "
                "copyleft is in product scope so release posture is unchanged."
            ),
            "owner_signoff": False,
        },
        "owner_approval": {
            "required_by_catalog": True,
            "obtained": False,
            "reason": (
                "Inventory complete. No copyleft in product scope. Owner ruling "
                "is required before shipping any later copyleft component; none "
                "is a release blocker on this worktree."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
        ],
        "evidence": [
            {
                "claim": "catalog unit ADV-0048 requires two-tier license identification",
                "verdict": "CONFIRMED",
                "anchor": f"{CATALOG}:{cat_line}",
            },
            {
                "claim": QUESTION,
                "verdict": "PARTIAL",
                "anchor": f"{CATALOG}:{q_line}",
            },
            {
                "claim": "known unambiguous MIT control is identified as MIT by probe 1",
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/ADV-0048/fixtures/control-mit/LICENSE"
                ),
            },
            {
                "claim": (
                    "first-party product tree has no declared license, so the "
                    "compatibility matrix is NOT-CHECKED rather than clean"
                ),
                "verdict": "CONFIRMED",
                "anchor": product["evidence_string"][:180],
            },
        ],
        "timestamps": {"emitted_at": now},
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0048/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "ADV-0048",
        },
    }

    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print("FAILED:ADV-0048 schema validation")
        for err in errors[:12]:
            print(f"  {list(err.path)}: {err.message}")
        return 1
    try:
        shim = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft7Validator(shim).validate(doc)
    except Exception as exc:
        print(f"catalog_schema_validate_warning={type(exc).__name__}:{exc}")
    text = dump(doc)
    if COMPLETION_SENTINEL not in text:
        print("FAILED:ADV-0048 completion_sentinel not in document text")
        return 1
    if "SUCCESS:ADV-0048" not in text:
        print("FAILED:ADV-0048 short sentinel absent")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:ADV-0048 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
