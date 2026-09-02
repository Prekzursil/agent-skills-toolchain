#!/usr/bin/env python3
"""Probe 2: real consumer exits on the same artifacts (mechanically different).

A reducer PASS with a consumer nonzero exit is the counterexample.
The negative control must be PASS from both the reducer (probe 1) and this consumer.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
from consumer import consume_file, live_delivery_gate, production_inventory  # noqa: E402
from reducer import reduce_file  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0001-predicate-passing-unusable-counterexample.json"
SCHEMA = REPO / "command-center/schema/refutation-record.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0001-probe2 {msg}")
    return 1


def main() -> int:
    cases = F.dump()
    attacks = [c for c in cases if not c["is_control"]]
    controls = [c for c in cases if c["is_control"]]
    if len(attacks) < 6 or len(controls) != 1:
        return fail(f"attacks={len(attacks)} controls={len(controls)}")

    inv = production_inventory()
    print("production_inventory " + json.dumps(
        {k: v["present"] for k, v in inv.items()}, sort_keys=True
    ))

    counterexamples = 0
    for case in attacks:
        path = REPO / case["path"]
        red = reduce_file(path)
        code, why = consume_file(path)
        live_ok, live_why = live_delivery_gate(path)
        print(
            f"fixture={case['id']} reducer={red['verdict']} "
            f"consumer_exit={code} consumer_why={why} "
            f"live_delivery_ok={live_ok} live_why={live_why}"
        )
        if red["verdict"] != "PASS":
            return fail(f"attack {case['id']} reducer not PASS")
        if code == 0:
            return fail(f"attack {case['id']} consumer unexpectedly succeeded")
        if live_ok:
            print(f"live_gate_also_passed_unusable={case['id']}")
        counterexamples += 1

    ctrl = controls[0]
    cpath = REPO / ctrl["path"]
    red_c = reduce_file(cpath)
    code_c, why_c = consume_file(cpath)
    live_c, live_cw = live_delivery_gate(cpath)
    print(
        f"fixture={ctrl['id']} reducer={red_c['verdict']} "
        f"consumer_exit={code_c} consumer_why={why_c} "
        f"live_delivery_ok={live_c} live_why={live_cw}"
    )
    if red_c["verdict"] != "PASS" or code_c != 0:
        return fail("negative control must PASS reducer and consumer")

    print(f"counterexamples={counterexamples}")
    print(f"control_both_pass={red_c['verdict'] == 'PASS' and code_c == 0}")
    if counterexamples < 6:
        return fail("need >=6 reducer-PASS/consumer-FAIL pairs")

    if ART.is_file() and SCHEMA.is_file():
        try:
            import jsonschema
        except ImportError:
            return fail("jsonschema not installed")
        doc = json.loads(ART.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        garbage_rejected = 0
        for g in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 200}):
            try:
                jsonschema.validate(g, schema)
            except jsonschema.ValidationError:
                garbage_rejected += 1
        print(f"schema_garbage_rejected={garbage_rejected}/3")
        if garbage_rejected != 3:
            return fail("declared schema accepts garbage")
        try:
            jsonschema.validate(doc, schema)
        except jsonschema.ValidationError as exc:
            return fail(f"live artifact fails schema: {exc.message}")
        print("schema_accepts_artifact=True")
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:ADV-0001" not in text:
            return fail("catalog sentinel fragment absent")
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"self-declared {doc.get('state')}")
    else:
        print("live_artifact_or_schema_absent_during_this_run=True")

    print("SUCCESS:ADV-0001-probe2 consumer fails six attacks and reads the control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
