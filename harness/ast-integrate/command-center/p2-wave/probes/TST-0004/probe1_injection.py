#!/usr/bin/env python3
"""Probe 1: inject a worker that exits 0 and writes nothing.

Live transcript of the missing-artifact injection. Classification must be
FAILED at condition 2, never SUCCESS. Also records the AST census of
returncode==0 sites so the evidence requirement is re-runnable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

UNIT = "TST-0004"


def main() -> int:
    pair = H.run_injection_pair()
    census = H.run_census()
    miss = pair["missing"]["classification"]
    print(
        json.dumps(
            {
                "probe": "probe1-injection",
                "unit_id": UNIT,
                "worker_exit_code": pair["missing"]["worker_exit_code"],
                "wrote_artifact": pair["missing"]["wrote_artifact"],
                "verdict": miss["verdict"],
                "failing_condition_id": miss["failing_condition_id"],
                "measure_gate": pair["missing"]["measure_gate"],
                "census_site_count": census["site_count"],
                "short_circuit_count": census["short_circuit_count"],
                "test_exit0_no_artifact_is_failed": pair[
                    "test_exit0_no_artifact_is_failed"
                ],
            },
            sort_keys=True,
        )
    )
    if pair["missing"]["worker_exit_code"] != 0:
        print("FAILED:TST-0004-probe1 injected worker did not exit 0")
        return 1
    if miss["verdict"] == "SUCCESS":
        print("FAILED:TST-0004-probe1 exit-0 missing artifact classified SUCCESS")
        return 1
    if miss["verdict"] != "FAILED" or miss["failing_condition_id"] != 2:
        print(
            "FAILED:TST-0004-probe1 expected FAILED at condition 2 "
            f"got {miss['verdict']} c={miss['failing_condition_id']}"
        )
        return 1
    if pair["missing"]["measure_gate"]["verdict"] != "FAILED":
        print("FAILED:TST-0004-probe1 measure existence gate did not FAIL")
        return 1
    if not pair["test_exit0_no_artifact_is_failed"]:
        print("FAILED:TST-0004-probe1 test_exit0_no_artifact_is_failed")
        return 1
    if not census["planted_control"]["fired_on_known_short_circuit"]:
        print("FAILED:TST-0004-probe1 planted short-circuit control silent")
        return 1
    print(
        f"injected_exit={pair['missing']['worker_exit_code']} "
        f"verdict={miss['verdict']} failing_condition_id="
        f"{miss['failing_condition_id']} "
        f"census_sites={census['site_count']} "
        f"short_circuits={census['short_circuit_count']}"
    )
    print("SUCCESS:TST-0004-probe1 injected exit-0 missing artifact is FAILED at c2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
