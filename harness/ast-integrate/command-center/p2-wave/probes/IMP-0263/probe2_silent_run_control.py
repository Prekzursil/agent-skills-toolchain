#!/usr/bin/env python3
"""Probe 2: negative control — strip the version check and detect silent-run."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.migrate import (  # noqa: E402
    MigrationRequired,
    execute_v2,
    is_silent_run,
    run_with_gate,
)

FIX = HERE / "fixtures"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0263-probe2 {msg}")
    return 1


def main() -> int:
    v1 = json.loads((FIX / "v1_recorded.json").read_text(encoding="utf-8"))
    ballots = json.loads((FIX / "ballots.json").read_text(encoding="utf-8"))

    production = run_with_gate(v1, ballots, version_check=True)
    if production["ok"]:
        return fail("production v2 runtime accepted un-migrated v1")
    if production["silent_run"]:
        return fail("production path classified as silent-run")
    if production.get("error") != "MigrationRequired":
        return fail(f"production error was {production.get('error')}, want MigrationRequired")

    try:
        execute_v2(v1, ballots, version_check=True)
        return fail("execute_v2(version_check=True) did not raise")
    except MigrationRequired as exc:
        production_exc = exc

    mutant = run_with_gate(v1, ballots, version_check=False)
    if not mutant["ok"]:
        return fail(f"mutant with version check removed did not run: {mutant}")
    mutant_result = mutant["result"]
    if mutant_result.get("decision") != "freeze":
        return fail(f"mutant did not produce a decision: {mutant_result}")
    if not mutant["silent_run"]:
        return fail("silent-run detector missed the mutant")
    if not is_silent_run(v1, mutant_result):
        return fail("is_silent_run False on mutant decision")
    if is_silent_run(v1, production_exc):
        return fail("is_silent_run True on production refusal")

    if is_silent_run(v1, production_exc) or not is_silent_run(v1, mutant_result):
        return fail("detector does not discriminate both states")

    print(
        json.dumps(
            {
                "production_refused": True,
                "production_silent_run": False,
                "mutant_ran": True,
                "mutant_decision": mutant_result.get("decision"),
                "mutant_silent_run_detected": True,
                "both_states": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0263-probe2 silent-run negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
