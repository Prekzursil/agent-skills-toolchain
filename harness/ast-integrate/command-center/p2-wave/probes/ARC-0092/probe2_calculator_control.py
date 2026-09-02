#!/usr/bin/env python3
"""Probe 2: calculator control, historical pairs, consumer call site.

A planted breaking change on the live A2 registry schema must classify
MAJOR before an identity NONE is trusted. Historical pairs (A2 1.0.0 cut,
plugin/marketplace/workflow identity, known-answer MAJOR and PATCH fixtures)
must match recorded history. A live bump report must validate against the
ARC-0092 contract; garbage must not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from calculator import calculator_control, extra_machine_checks  # noqa: E402
from historical import historical_ok, live_registry_schema  # noqa: E402

ART = REPO / "command-center/phase4/contracts/ARC-0092.json"


def _report(pair: dict) -> dict:
    v = pair["verdict"]
    return {
        "contract_id": "ARC-0092",
        "artifact_class": pair["artifact_class"],
        "from_ref": pair["from_ref"],
        "to_ref": pair["to_ref"],
        "required_bump": v["required_bump"],
        "changes": v["changes"],
        "computed_not_asserted": True,
        "matches_recorded_history": pair["matches_recorded_history"],
    }


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0092-probe2 contract missing")
        return 1
    contract = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:ARC-0092" not in json.dumps(contract):
        print("FAILED:ARC-0092-probe2 sentinel absent")
        return 1
    if str(contract.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0092-probe2 self-declared {contract.get('state')}")
        return 1

    control = calculator_control(live_registry_schema())
    extra = extra_machine_checks()
    hist = historical_ok()
    print(
        json.dumps(
            {
                "control_pass": control["pass"],
                "planted_kind": control["planted_kind"],
                "detected_breaking": control["detected_breaking"],
                "identity_none": control["identity_none"],
                "extra_pass": extra["pass"],
                "historical_pass": hist["pass"],
                "historical_pairs": hist["pair_count"],
            },
            sort_keys=True,
        )
    )
    if not control["pass"]:
        print("FAILED:ARC-0092-probe2 calculator-control")
        return 1
    if not extra["pass"]:
        print("FAILED:ARC-0092-probe2 extra-machine-checks")
        return 1
    if not hist["pass"]:
        print("FAILED:ARC-0092-probe2 historical-mismatch")
        return 1

    Draft202012Validator.check_schema(contract)
    validator = Draft202012Validator(contract)
    report = _report(hist["pairs"][0])
    errs = list(validator.iter_errors(report))
    if errs:
        print("FAILED:ARC-0092-probe2 consumer rejected live report", errs[0].message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"contract_id": "ARC-0092"},
    ):
        g_errs = list(validator.iter_errors(garbage))
        if not g_errs:
            print("FAILED:ARC-0092-probe2 contract accepted garbage")
            return 1
    print("consumer_call_site_ok=True garbage_rejected=True")
    print("SUCCESS:ARC-0092-probe2 calculator-control historical consumer-call-site")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
