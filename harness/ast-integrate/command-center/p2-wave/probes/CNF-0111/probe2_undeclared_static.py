#!/usr/bin/env python3
"""Named probe 2: undeclared-action finding, static scan, detector both-states.

Mechanically different from probe 1: does not compare the 4x2 grant matrix.
It (a) checks the write-outside-root undeclared cell, (b) re-scans product
enforcement candidates, (c) validates the artifact against the schema,
(d) asserts credential presence-only, (e) fail-open mutant of Gate must be
classified permission-not-enforced (detector control).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from enforcement import Gate, NullGate, PERMISSIONS  # noqa: E402
from measure import empty_cells, measure  # noqa: E402
from product_scan import scan  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0111-runtime-permission-enforcement.json"
SCHEMA = REPO / "command-center/schema/permission-report.schema.json"
UID = "CNF-0111"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0111-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != UID:
        print("FAILED:CNF-0111-probe2 unit_id", doc.get("unit_id"))
        return 1
    catalog = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    sentinel = None
    for unit in catalog.get("work_units") or []:
        if unit.get("id") == UID:
            sentinel = unit.get("completion_sentinel")
            break
    if not sentinel or sentinel not in text:
        print("FAILED:CNF-0111-probe2 catalog sentinel absent")
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = list(validator.iter_errors(doc))
    if errs:
        print("FAILED:CNF-0111-probe2 schema", errs[0].message)
        return 1
    for garbage in ({"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0111-probe2 schema accepts garbage")
            return 1

    live = measure()
    if empty_cells(live["matrix"]) or empty_cells(live["detector_control"]):
        print("FAILED:CNF-0111-probe2 empty cells")
        return 1

    product_outside = next(
        c for c in live["matrix"] if c["action"] == "write-outside-root"
    )
    detector_outside = next(
        c for c in live["detector_control"] if c["action"] == "write-outside-root"
    )
    if product_outside["observed"] != "succeeded":
        print("FAILED:CNF-0111-probe2 product outside-root did not succeed (fail-open expected)")
        return 1
    if detector_outside["observed"] != "blocked":
        print("FAILED:CNF-0111-probe2 detector outside-root not blocked")
        return 1
    if product_outside["enforcement_outcome"] != "undeclared-action-succeeded":
        print("FAILED:CNF-0111-probe2 undeclared outcome", product_outside["enforcement_outcome"])
        return 1

    classes = {f["classification"] for f in live["findings"]}
    if "undeclared-action" not in classes and "excessive-permission" not in classes:
        print("FAILED:CNF-0111-probe2 missing undeclared/excessive finding")
        return 1
    if "permission-not-enforced" not in classes:
        print("FAILED:CNF-0111-probe2 missing permission-not-enforced finding")
        return 1

    cred = live["credential_probe"]
    if cred["mode"] != "presence-only" or cred["value_read"] or cred["value_printed"]:
        print("FAILED:CNF-0111-probe2 credential leak")
        return 1
    if doc.get("credential_value_printed") is not False:
        print("FAILED:CNF-0111-probe2 artifact printed a credential value")
        return 1

    static = scan(REPO)
    if static["enforcement_module_present"]:
        print("FAILED:CNF-0111-probe2 unexpected product enforcement module present")
        print(json.dumps(static["paths_probed"], indent=2))
        return 1
    if static["enforcement_module_present"] != doc["product_runtime"]["enforcement_module_present"]:
        print("FAILED:CNF-0111-probe2 product_runtime drifted")
        return 1

    # Both-states on the instrument: fail-open Gate must not block.
    open_gate = NullGate(PERMISSIONS)
    closed = Gate(PERMISSIONS, enabled=True)
    if open_gate.enabled:
        print("FAILED:CNF-0111-probe2 NullGate enabled")
        return 1
    try:
        closed.check("network", "connect")
    except Exception as exc:
        print("FAILED:CNF-0111-probe2 granted detector raised", exc)
        return 1
    narrowed = Gate([p for p in PERMISSIONS if p != "network"], enabled=True)
    blocked = False
    try:
        narrowed.check("network", "connect")
    except Exception:
        blocked = True
    if not blocked:
        print("FAILED:CNF-0111-probe2 fail-closed mutant did not block")
        return 1
    fail_open = Gate([p for p in PERMISSIONS if p != "network"], enabled=False)
    fail_open.check("network", "connect")

    if doc.get("empty_cells") != 0:
        print("FAILED:CNF-0111-probe2 artifact empty_cells")
        return 1

    summary = {
        "probe": "probe2-undeclared-static",
        "unit_id": UID,
        "pass": True,
        "schema_ok": True,
        "garbage_rejected": True,
        "undeclared_product_succeeded": True,
        "undeclared_detector_blocked": True,
        "credential_presence_only": True,
        "product_enforcer_present": static["enforcement_module_present"],
        "findings": sorted(classes),
        "fail_open_mutant_allows": True,
        "fail_closed_mutant_blocks": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "schema_ok=True undeclared_finding=True cred_presence_only=True "
        "static_absent=True both_states=True"
    )
    print("SUCCESS:CNF-0111-probe2 undeclared static detector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
