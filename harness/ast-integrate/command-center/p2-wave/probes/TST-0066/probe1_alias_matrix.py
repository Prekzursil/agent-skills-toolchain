#!/usr/bin/env python3
"""Probe 1: both aliases against every guard (control + live estate).

Fires trailing-dot and 8.3 forms at deny, allowlist, and containment.
Records ACCEPT/REJECT. Requires canonical guards to hold and the estate
census to have attempted both aliases on each live guard.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import evaluate as E  # noqa: E402

OUT = HERE / "probe1-alias-matrix.raw.json"


def main() -> int:
    report = E.evaluate()
    payload = {
        "probe": "probe1-alias-matrix",
        "unit_id": "TST-0066",
        "pass": report["pass"],
        "failed": report["failed"],
        "tests": report["tests"],
        "string_comparing_estate_guards": report["string_comparing_estate_guards"],
        "estate_classification": [
            {
                "guard_id": g["guard_id"],
                "kind": g["kind"],
                "compares_path_strings": g["compares_path_strings"],
                "policy": g["policy"],
                "n_shots": len(g["shots"]),
            }
            for g in report["estate_classification"]
        ],
        "control_shots": report["control_shots"],
        "estate_shots": report["estate_shots"],
        "identities": report["identities"],
    }
    art_err = E.artifact_error()
    if art_err:
        payload["pass"] = False
        payload["error"] = art_err
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({k: payload[k] for k in ("pass", "error", "failed")}, sort_keys=True))
        print(f"FAILED:TST-0066-probe1 {art_err}")
        return 1
    if not report["pass"]:
        payload["error"] = "required tests failed"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(payload["failed"], indent=2))
        print("FAILED:TST-0066-probe1 required tests failed")
        return 1
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    names = [g["guard_id"] for g in report["string_comparing_estate_guards"]]
    print(
        "estate_string_guards="
        + ",".join(names)
        + " tests_pass="
        + str(len(report["tests"]))
        + " control_shots="
        + str(len(report["control_shots"]))
        + " estate_shots="
        + str(len(report["estate_shots"]))
    )
    print("SUCCESS:TST-0066-probe1 alias matrix both aliases per guard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
