#!/usr/bin/env python3
"""Probe 2: both-states control — missing required `name` must be rejected."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from validator import format_verbatim, validate_plugin_manifest  # noqa: E402

FIX = HERE / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def main() -> int:
    present = validate_plugin_manifest(load("valid-minimal.json"))
    missing = validate_plugin_manifest(load("missing-name.json"))
    missing_verbatim = format_verbatim("MISSING-REQUIRED-NAME", missing)
    present_verbatim = format_verbatim("REQUIRED-NAME-PRESENT", present)

    name_err = any("name" in e.lower() and "required" in e.lower() for e in missing["errors"])
    checks = [
        ("present_valid", present["valid"] is True),
        ("present_has_name", "name" in present["instance_keys"]),
        ("missing_invalid", missing["valid"] is False),
        ("missing_reports_name", name_err or "name" in missing["missing_required"]),
        ("both_states_differ", present["valid"] is not missing["valid"]),
        ("silent_in_both_states", not (present["valid"] is False and missing["valid"] is False)),
    ]
    failed = [name for name, ok in checks if not ok]
    payload = {
        "probe": "probe2_missing_required",
        "unit_id": "RES-0007",
        "pass": not failed,
        "failed": failed,
        "name_present": present,
        "name_missing": missing,
        "both_states": {
            "present_accepted": present["valid"],
            "missing_rejected": not missing["valid"],
        },
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(missing_verbatim)
    print(present_verbatim)
    if failed:
        print("FAILED:RES-0007-probe2 " + ",".join(failed))
        return 1
    print("SUCCESS:RES-0007-probe2 missing required name rejected; present name accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
