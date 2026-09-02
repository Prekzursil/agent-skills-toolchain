#!/usr/bin/env python3
"""Probe 1: both-states control on the recorded zero-hooks manifest.

The known-broken hooks.json ($schema key) must be rejected. The known-good
working plugin.json must be accepted. Outcomes are recorded, not narrated.
A schema that accepts both states measures nothing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from jsonschema import Draft202012Validator  # noqa: E402

from clauses import CLAUSE_STRINGS, CONTRACT_REL, SENTINEL, ZERO_HOOKS_RULE  # noqa: E402
from consumer import (  # noqa: E402
    CONTRACT_PATH,
    load_contract,
    validate_hooks_file,
    validate_plugin,
)

FIX = HERE / "fixtures"
WORKING = FIX / "working" / "plugin.json"
BROKEN = FIX / "historical-zero-hooks" / "plugin.json"
BROKEN_HOOKS = FIX / "historical-zero-hooks" / "hooks.json"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0078-probe1 {msg}")
    return 1


def main() -> int:
    if not CONTRACT_PATH.is_file():
        return fail(f"contract missing {CONTRACT_REL}")
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    missing = [c for c in CLAUSE_STRINGS if c not in text]
    if missing:
        return fail(f"contract missing clauses {missing[:2]}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    if ZERO_HOOKS_RULE not in text:
        return fail("zero-hooks rule absent")

    contract = load_contract()
    try:
        Draft202012Validator.check_schema(contract)
    except Exception as exc:
        return fail(f"check_schema {type(exc).__name__}: {exc}")
    v = Draft202012Validator(contract)
    for g in ({}, {"totally": "unrelated"}, {"name": "nope"}):
        if not list(v.iter_errors(g)):
            return fail("schema-document-vacuous")

    good = validate_plugin(WORKING, host_os="linux", contract=contract)
    bad = validate_plugin(BROKEN, host_os="linux", contract=contract)
    hooks_only = validate_hooks_file(BROKEN_HOOKS, contract=contract)

    if not good.ok:
        return fail(f"working manifest rejected: {good.as_dict()}")
    if bad.ok:
        return fail("historical zero-hooks manifest was accepted")
    if hooks_only.ok:
        return fail("historical hooks.json with $schema was accepted")

    codes = {i.code for i in bad.issues} | {i.code for i in hooks_only.issues}
    if "zero-hooks-unknown-field" not in codes:
        return fail(f"broken case not classified as zero-hooks; codes={sorted(codes)}")

    extra = json.loads(WORKING.read_text(encoding="utf-8"))
    extra["unknown_top_level"] = "should-reject"
    extra_errs = list(v.iter_errors(extra))
    if not extra_errs:
        return fail("strict policy accepted an unprefixed unknown key")

    record = {
        "probe": "probe1-both-states",
        "unit_id": "ARC-0078",
        "call_site": "command-center/p2-wave/probes/ARC-0078/consumer.py::validate_plugin",
        "working": good.as_dict(),
        "historical_zero_hooks": bad.as_dict(),
        "historical_hooks_file": hooks_only.as_dict(),
        "unknown_unprefixed_key_rejected": True,
        "schema_discriminates_garbage": True,
    }
    print(json.dumps(record, indent=2, sort_keys=True))
    print(
        f"working_ok={good.ok} broken_ok={bad.ok} "
        f"zero_hooks_codes={sorted(codes)}"
    )
    print("SUCCESS:ARC-0078-probe1 both-states known-broken rejected known-good accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
