#!/usr/bin/env python3
"""IMP-0341 probe 1: entry schema requires a settling experiment.

A missing or empty settling_experiment is schema-invalid. A vague string is
still schema-present (the audit in probe 2 must fail it). Capture must not
invent an experiment for a question that did not name one.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.outcomes.unresolved import (  # noqa: E402
    capture,
    load_path,
    schema_errors,
    schema_errors_entry,
)

UNIT = "IMP-0341"
ART = REPO / "command-center" / "receipts" / "IMP-0341.json"
MIXED = HERE / "fixtures" / "mixed-ledger.json"
COUNCIL = HERE / "fixtures" / "council-artifact.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0341-probe1 {msg}")
    return 1


def concrete_entry() -> dict:
    return {
        "id": "schema-ok",
        "question": "Does the schema accept a named settling experiment object?",
        "settling_experiment": {
            "command": "python3 -B command-center/p2-wave/probes/IMP-0341/fixtures/oracle_ok.py",
            "inputs": ["command-center/p2-wave/probes/IMP-0341/fixtures/input.txt"],
            "oracle": {"kind": "exit-code", "expect": 0},
        },
    }


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(receipt)
    if "SUCCESS:IMP-0341" not in text:
        return fail("sentinel absent")
    if str(receipt.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {receipt.get('state')}")

    good = concrete_entry()
    if schema_errors_entry(good):
        return fail(f"concrete entry schema-invalid {schema_errors_entry(good)}")
    if schema_errors([good]):
        return fail("concrete ledger schema-invalid")

    missing = {"id": "no-exp", "question": "What remains after the council adjourned?"}
    miss_errs = schema_errors_entry(missing)
    if not any("missing settling_experiment" in e for e in miss_errs):
        return fail(f"missing experiment not rejected: {miss_errs}")

    empty = dict(good)
    empty["settling_experiment"] = ""
    empty_errs = schema_errors_entry(empty)
    if not any("empty" in e for e in empty_errs):
        return fail(f"empty experiment not rejected: {empty_errs}")

    vacant = dict(good)
    vacant["settling_experiment"] = {}
    vacant_errs = schema_errors_entry(vacant)
    if not any("empty" in e or "command missing" in e for e in vacant_errs):
        return fail(f"vacuous object experiment not rejected: {vacant_errs}")

    dropped = deepcopy(good)
    del dropped["settling_experiment"]
    drop_errs = schema_errors([dropped])
    if not drop_errs:
        return fail("mutant with deleted settling_experiment accepted")

    vague = {
        "id": "vague",
        "question": "What else should the council still worry about later?",
        "settling_experiment": "investigate further",
    }
    vague_schema = schema_errors_entry(vague)
    if vague_schema:
        return fail(f"vague string must be schema-present; got {vague_schema}")

    captured = capture(json.loads(COUNCIL.read_text(encoding="utf-8")), source="council")
    if len(captured) < 3:
        return fail(f"capture under-count {len(captured)}")
    invented = [e for e in captured if e.get("id") == "CQ-MISSING-EXPERIMENT" and "settling_experiment" in e]
    if invented:
        return fail("capture invented a settling experiment")
    missing_cap = next(e for e in captured if e.get("id") == "CQ-MISSING-EXPERIMENT")
    cap_errs = schema_errors_entry(missing_cap)
    if not any("missing settling_experiment" in e for e in cap_errs):
        return fail(f"captured unnamed leftover not schema-invalid: {cap_errs}")

    mixed = load_path(MIXED)
    mixed_errs = schema_errors(mixed)
    if mixed_errs:
        return fail(f"mixed ledger should be schema-valid (audit is probe2): {mixed_errs}")

    payload = {
        "capture_count": len(captured),
        "capture_does_not_invent_experiment": True,
        "concrete_schema_ok": True,
        "empty_rejected": True,
        "missing_rejected": True,
        "mutant_rejected": True,
        "pass": True,
        "probe": "probe1-schema-requires-settling-experiment",
        "unit_id": UNIT,
        "vague_string_schema_ok": True,
        "vacuous_object_rejected": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "missing_rejected=True vague_schema_ok=True "
        "capture_no_invent=True mutant_rejected=True"
    )
    print("SUCCESS:IMP-0341-probe1 schema requires settling_experiment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
