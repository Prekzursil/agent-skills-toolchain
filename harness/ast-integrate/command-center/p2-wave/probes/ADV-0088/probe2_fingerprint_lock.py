#!/usr/bin/env python3
"""Probe 2: fingerprint the measure before/after; require pre-change compare.

Mechanically different from probe 1: this probe does not use KEEP/REVERT as
its primary signal. It hashes measure files, checks product trees for a live
lock, and requires the artifact to parse against the catalog schema.
Absence of a product fingerprint requirement is the finding.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import experiment as E  # noqa: E402

OUT = "command-center/adversarial/ADV-0088-self-improvement-measure-tampering.json"
SCHEMA = "command-center/schema/benchmark-integrity.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)
ALLOWED = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0088-probe2 {msg}")
    return 1


def catalog_sentinel() -> str:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "ADV-0088":
            return str(unit["completion_sentinel"])
    raise SystemExit("FAILED:ADV-0088-probe2 catalog unit missing")


def main() -> int:
    matrix = E.run_matrix(REPO)
    payload = E.probe2_payload(matrix)
    print(E.dumps(payload))
    if not matrix["tampers_change_fingerprint"]:
        return fail("a measure-only tamper left the fingerprint unchanged")
    if not matrix["genuine_fingerprint_stable"]:
        return fail("genuine SUT fix changed the measure fingerprint")
    if not matrix["locked_tampers_reverted"] or not matrix["genuine_locked_keep"]:
        return fail("locked loop does not compare against the pre-change measure")
    if not matrix["reject_all_is_not_credited"]:
        return fail("cannot distinguish locked KEEP-genuine from reject-all")
    product = matrix["product"]
    if product.get("product_fingerprint_lock_present"):
        return fail("unexpected product fingerprint lock; re-derive before claiming absence")
    if not matrix["control_holds"]:
        return fail("control_holds is false")

    out = REPO / OUT
    schema_path = REPO / SCHEMA
    if not out.is_file() or out.stat().st_size <= 0:
        return fail("artifact absent")
    try:
        text = out.read_text(encoding="utf-8")
        doc = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return fail(f"unparseable:{type(exc).__name__}")
    sentinel = catalog_sentinel()
    if sentinel not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("schema errors:")
        for err in errs[:12]:
            print(" ", list(err.path), err.message)
        return fail("schema-invalid")
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            return fail("schema accepted garbage")
    named = doc.get("named_probes") or []
    if len(named) < 2:
        return fail("named probes missing from artifact")
    for item in named:
        if not str(item.get("raw_output") or "").strip():
            return fail("named probe raw_output empty")
    targets = doc.get("targets") or []
    if not targets:
        return fail("no targets")
    seen = set()
    for target in targets:
        tid = target.get("target_id")
        verdict = target.get("verdict")
        if tid in seen:
            return fail(f"duplicate target {tid}")
        seen.add(tid)
        if verdict not in ALLOWED:
            return fail(f"illegal verdict {verdict}")
    controls = doc.get("negative_controls") or []
    if not controls:
        return fail("negative_controls missing")
    if not all(
        c.get("fired_on_bad_state") is True and c.get("silent_on_good_state") is True
        for c in controls
        if isinstance(c, dict)
    ):
        return fail("negative control both-states not recorded")
    tests = doc.get("tests") or []
    if any(t.get("id") == "T-GENUINE-IMPROVEMENT-ACCEPTED" and t.get("result") != "PASS" for t in tests):
        return fail("required genuine-improvement control not PASS")
    print(
        f"schema_ok=True fingerprint_delta=True product_lock={product['product_fingerprint_lock_present']} "
        f"scanned={product['scanned_files']}"
    )
    print("SUCCESS:ADV-0088-probe2 fingerprint lock and schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
