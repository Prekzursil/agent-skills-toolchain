#!/usr/bin/env python3
"""Named probe 2: detector control, staleness, register relabel, schema mutants."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from emit_receipt import load_local_schema, validate_record  # noqa: E402
from reproduce import (  # noqa: E402
    largest_three,
    load_register,
    plant_timeout_leak,
    quota_not_refuted,
    RELABELLED_PATH,
    reproduce_all,
    rollback_detached,
    sha256_file,
    stale_fixed_ok,
)

ART = REPO / "command-center/receipts/CNF-0158.json"
SCHEMA = HERE / "confirmation-record.local.schema.json"


def _fail(msg: str) -> int:
    print(f"FAILED:CNF-0158-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return _fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema = load_local_schema() if SCHEMA.is_file() else json.loads(SCHEMA.read_text(encoding="utf-8"))
    try:
        validate_record(doc, schema)
    except jsonschema.ValidationError as exc:
        return _fail(f"receipt schema invalid: {exc.message}")

    src_fp = str((doc.get("source_probe") or {}).get("fingerprint") or "")
    ver_fp = str((doc.get("verifier_probe") or {}).get("fingerprint") or "")
    if src_fp == ver_fp:
        return _fail("same-probe-rerun fingerprints identical")
    live_src = sha256_file(HERE / "probe1_reproduce.py")
    live_ver = sha256_file(HERE / "probe2_controls.py")
    if src_fp != live_src:
        return _fail("source_probe fingerprint stale vs probe1 file")
    if ver_fp != live_ver:
        return _fail("verifier_probe fingerprint stale vs probe2 file")

    mutant = copy.deepcopy(doc)
    mutant["verdict"] = "CONFIRMED"
    mutant["source_probe"] = {}
    try:
        jsonschema.Draft7Validator(schema).validate(mutant)
    except jsonschema.ValidationError:
        pass
    else:
        return _fail("unsourced CONFIRMED validated (schema hole still open)")

    mutant2 = copy.deepcopy(doc)
    mutant2["verdict"] = "CONFIRMED"
    mutant2["source_probe"] = copy.deepcopy(doc["verifier_probe"])
    mutant2["verifier_probe"] = copy.deepcopy(doc["verifier_probe"])
    try:
        validate_record(mutant2, schema)
    except jsonschema.ValidationError:
        pass
    else:
        return _fail("same-probe-rerun CONFIRMED accepted")

    planted = plant_timeout_leak()
    if not planted["pass"]:
        return _fail(f"planted leak not detected: {planted}")

    result = reproduce_all()
    stale = stale_fixed_ok(result)
    if not stale or not all(c["pass"] for c in stale):
        return _fail(f"FIXED staleness failed: {stale}")

    if not result["relabel_ok"]:
        return _fail("non-REPRODUCED entries left OPEN")
    if not RELABELLED_PATH.is_file():
        return _fail("relabelled register missing")
    rel = json.loads(RELABELLED_PATH.read_text(encoding="utf-8"))
    original = {e["id"]: e["claimed_status"] for e in load_register()["leaks"]}
    for entry in rel["leaks"]:
        live = next(r for r in result["rows"] if r["id"] == entry["id"])
        if live["overall"] != "REPRODUCED" and entry["claimed_status"] == original[entry["id"]] == "OPEN":
            return _fail(f"{entry['id']} not relabelled (still OPEN)")
        if live["overall"] != "REPRODUCED" and entry["claimed_status"] == "OPEN":
            return _fail(f"{entry['id']} silent OPEN after confirmation")
        if entry.get("relabelled_by") != "CNF-0158" and live["overall"] != "REPRODUCED":
            return _fail(f"{entry['id']} missing relabelled_by")

    quota = quota_not_refuted()
    if not quota["pass"]:
        return _fail(f"quota converted: {quota}")

    rolled = rollback_detached()
    if not rolled["pass"]:
        return _fail(f"rollback rehearsal failed: {rolled}")

    for leak_id in largest_three(result):
        row = next(r for r in result["rows"] if r["id"] == leak_id)
        again = reproduce_all()
        again_row = next(r for r in again["rows"] if r["id"] == leak_id)
        if again_row["overall"] != row["overall"]:
            return _fail(f"reviewer re-run drifted {leak_id}")

    att = str(doc.get("blinding_attestation_hash") or "")
    if len(att) != 64:
        return _fail("attestation hash missing")

    print(
        json.dumps(
            {
                "probe": "probe2-controls",
                "unit_id": "CNF-0158",
                "pass": True,
                "planted_detected": planted["planted_detected"],
                "fixed_markers": stale,
                "relabel_ok": True,
                "quota_not_refuted": True,
                "rollback_ok": True,
                "unsourced_confirmed_rejected": True,
                "same_probe_rerun_rejected": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0158-probe2 detector/staleness/relabel/schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
