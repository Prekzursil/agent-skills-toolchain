#!/usr/bin/env python3
"""Probe 2: enforcement control, validation, and overclaim mutant."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from enforcement import (  # noqa: E402
    DeclarationError,
    Permission,
    evaluate,
    invoke,
)
from reconcile import (  # noqa: E402
    label_declared_not_observed,
    mutant_unexercised_as_overgrant,
)
from window import (  # noqa: E402
    both_states_enforcement,
    credential_wildcard_rejected,
    run_adequate,
)

ART = REPO / "command-center/phase4/conformance/ARC-0108.json"
SCHEMA = REPO / "command-center/schema/conformance-report.schema.json"
SENTINEL = "SUCCESS:ARC-0108"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def _fail(msg: str) -> int:
    print(f"FAILED:ARC-0108-probe2 {msg}")
    return 1


def main() -> int:
    states = both_states_enforcement()
    print(json.dumps(states, sort_keys=True))
    if not states["fires_on_under_declaration"]:
        return _fail("undeclared Write did not fire DENY")
    if not states["silent_on_grant"]:
        return _fail("authorized Write was not ALLOW")
    if not states["deny_wins"]:
        return _fail("deny-rule did not win over grant")
    if not credential_wildcard_rejected():
        return _fail("credential:* grant was not rejected at validation")

    rec = invoke(
        "cap.sneak",
        "plugin",
        [Permission("tool", "Read")],
        Permission("tool", "Write"),
        side_effect=lambda: (_ for _ in ()).throw(RuntimeError("side effect on DENY")),
    )
    if rec.decision != "DENY":
        return _fail("invoke allowed undeclared Write")

    escaped = evaluate(
        [Permission("path", "**")],
        Permission("path", "../secret"),
    )
    if escaped.verdict != "DENY":
        return _fail("path-escape was not denied")

    if label_declared_not_observed(True) == mutant_unexercised_as_overgrant(True):
        return _fail("production classifier equals OVER-GRANT mutant")
    if label_declared_not_observed(True) != "UNEXERCISED":
        return _fail("production label is not UNEXERCISED")
    if label_declared_not_observed(False) != "NOT-CHECKED":
        return _fail("inadequate sample must be NOT-CHECKED")

    try:
        evaluate([], Permission("tool", "Read"))
        return _fail("empty declaration was accepted")
    except DeclarationError:
        pass

    adequate = run_adequate()
    sneak_deny = [
        r
        for r in adequate["records"]
        if r["capability_id"] == "cap.sneak"
        and r["permission"] == "tool:Write"
        and r["decision"] == "DENY"
    ]
    if not sneak_deny:
        return _fail("adequate window missing sneak Write DENY record")
    if any(":invoke" not in r["enforcement_point"] for r in adequate["records"]):
        return _fail("record bypassed invoke()")

    if not ART.is_file():
        return _fail("conformance artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return _fail("sentinel absent")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return _fail(f"self-declared:{st}")
    if "compliance_percent" in doc or "compliance_percentage" in doc:
        return _fail("artifact uses a percentage verdict")
    dirs = doc.get("directions") or {}
    if "declared_not_observed" not in dirs or "observed_not_declared" not in dirs:
        return _fail("artifact missing both direction lists")
    if any(
        str(r.get("label") or "") == "OVER-GRANT"
        for r in dirs.get("declared_not_observed") or []
    ):
        return _fail("artifact labels UNEXERCISED as OVER-GRANT")
    ep = doc.get("enforcement_point") or {}
    if ep.get("function") != "invoke":
        return _fail("artifact enforcement_point is not invoke")
    parser = doc.get("parser") or {}
    if not parser.get("name") or not parser.get("version"):
        return _fail("artifact parser identity missing")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        return _fail(f"schema {errs[0].message}")
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"x": "x" * 2000}):
        if not list(validator.iter_errors(garbage)):
            return _fail("schema accepted garbage")

    tests = {t.get("id"): t for t in doc.get("tests") or []}
    for tid in ("T-BOTH-DIRECTIONS", "T-ENFORCEMENT", "T-SAMPLE-ADEQUACY"):
        if tests.get(tid, {}).get("result") != "PASS":
            return _fail(f"test {tid} not PASS")

    print(
        "enforcement fires_on_under_declaration=True "
        "silent_on_grant=True deny_wins=True "
        "unexercised_not_overgrant=True schema_ok=True"
    )
    print("SUCCESS:ARC-0108-probe2 enforcement control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
