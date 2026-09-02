#!/usr/bin/env python3
"""Probe 2: detector control — reviewer re-runs the known-broken fixtures.

Required:
  * disable one hook; the diff names its absence; it remains in the manifest
  * $schema zero-load fires nothing (installed is not loaded)
  * silent non-zero exit is distinct from never-fires
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import inventory as inv  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0054-hook-firing-diff.json"
SCHEMA = REPO / "command-center/schema/regression-delta.schema.json"


def main() -> int:
    m = inv.measure()
    print(
        json.dumps(
            {
                "probe": "probe2-detector-control",
                "unit_id": "CNF-0054",
                "disable_detected": m["disable_detected"],
                "disable_missing": m["disable_delta"]["missing_from_after"],
                "disabled_still_in_manifest": "hook.pre-tool" in m["disabled"]["manifest_hook_ids"],
                "schema_detected": m["schema_detected"],
                "schema_firing_count": m["schema_zero"]["firing_count"],
                "schema_loader_mode": m["schema_zero"]["loader_mode"],
                "naive_manifest_count_blind": m["naive_manifest_count_blind"],
                "distinguished_silent_vs_never": m["distinguished_silent_vs_never"],
                "silent_nonzero": m["classify"]["silent_nonzero"],
                "never_fired_but_installed": m["classify"]["never_fired_but_installed"],
            },
            sort_keys=True,
        )
    )
    if not m["disable_detected"]:
        print("FAILED:CNF-0054-probe2 disable control did not fire")
        return 1
    if m["disable_delta"]["missing_from_after"] != ["hook.pre-tool"]:
        print("FAILED:CNF-0054-probe2 missing set", m["disable_delta"]["missing_from_after"])
        return 1
    if not m["schema_detected"] or m["schema_zero"]["firing_count"] != 0:
        print("FAILED:CNF-0054-probe2 schema-zero-load not detected")
        return 1
    if not m["naive_manifest_count_blind"]:
        print("FAILED:CNF-0054-probe2 naive count unexpectedly differed")
        return 1
    if not m["distinguished_silent_vs_never"]:
        print("FAILED:CNF-0054-probe2 failed to distinguish silent-nonzero from never-fires")
        return 1
    stop_nonzero = any(
        r["hook_id"] == "hook.stop" and int(r["exit_code"]) != 0
        for r in m["classify"]["silent_nonzero"]
    )
    if not stop_nonzero:
        print("FAILED:CNF-0054-probe2 hook.stop not recorded as fired-nonzero")
        return 1
    if "hook.stop" in m["classify"]["never_fired_but_installed"]:
        print("FAILED:CNF-0054-probe2 hook.stop misclassified as never-fires")
        return 1
    if "hook.notification" in m["classify"]["fired_hook_ids"]:
        print("FAILED:CNF-0054-probe2 hook.notification fired (should be disabled)")
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft7Validator(schema)
    for garbage in ({}, {"passing_tests": 999999}, {"blob": "x" * 2000}):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0054-probe2 schema accepted garbage")
            return 1

    if not ART.is_file():
        print("FAILED:CNF-0054-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0054-probe2 self-declared", doc.get("state"))
        return 1
    if inv.SENTINEL not in text:
        print("FAILED:CNF-0054-probe2 sentinel absent")
        return 1
    ctrl = (doc.get("controls") or {}).get("deliberate_disable") or {}
    if ctrl.get("detected") is not True:
        print("FAILED:CNF-0054-probe2 artifact control not detected")
        return 1
    missing = (ctrl.get("delta") or {}).get("missing_from_after") or []
    if "hook.pre-tool" not in missing:
        print("FAILED:CNF-0054-probe2 artifact missing set lacks disabled hook")
        return 1
    installed = (doc.get("controls") or {}).get("installed_is_not_loaded") or {}
    if installed.get("detected") is not True:
        print("FAILED:CNF-0054-probe2 artifact installed-not-loaded not detected")
        return 1
    art_errors = list(validator.iter_errors(doc))
    if art_errors:
        print("FAILED:CNF-0054-probe2 artifact schema", art_errors[0].message)
        return 1
    print("SUCCESS:CNF-0054-probe2 detector control on known-broken fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
