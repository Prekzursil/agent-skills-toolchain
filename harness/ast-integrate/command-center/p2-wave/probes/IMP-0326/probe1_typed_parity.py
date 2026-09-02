#!/usr/bin/env python3
"""Probe 1: typed SDK results + live SDK/CLI artifact-key parity.

Prints the set-difference both directions. End-to-end SDK-driven council.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.sdk import (  # noqa: E402
    ARTIFACT_KEYS,
    CouncilResult,
    CouncilSDK,
    CouncilSpec,
    Decision,
    DecisionStatus,
    assert_typed_result,
    sdk_reachable_keys,
    surface_parity,
)

SDK_CLI = REPO / "tools" / "council" / "sdk.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0326/probe1_typed_parity.py"
)


def _cli_inspect(run_dir: Path) -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(SDK_CLI),
            "inspect",
            "--run-dir",
            str(run_dir),
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"FAILED:IMP-0326-probe1 cli inspect rc={proc.returncode} "
            f"stderr={proc.stderr[-500:]}"
        )
    data = json.loads(proc.stdout)
    if not isinstance(data, dict):
        raise SystemExit("FAILED:IMP-0326-probe1 CLI inspect did not emit an object")
    return data


def main() -> int:
    sdk = CouncilSDK()
    spec = sdk.build_fixture()
    if type(spec) is not CouncilSpec:
        print(f"FAILED:IMP-0326-probe1 builder returned {type(spec)!r}")
        return 1
    result = sdk.execute(spec, run_id="imp-0326-probe1")
    try:
        assert_typed_result(result)
    except TypeError as exc:
        print(f"FAILED:IMP-0326-probe1 typed-result {exc}")
        return 1
    if isinstance(result, str) or type(result) is not CouncilResult:
        print("FAILED:IMP-0326-probe1 execute was stringly typed")
        return 1
    if type(result.decision) is not Decision:
        print("FAILED:IMP-0326-probe1 decision is not Decision")
        return 1
    if type(result.decision.status) is not DecisionStatus:
        print("FAILED:IMP-0326-probe1 decision.status is not DecisionStatus")
        return 1

    inspection = sdk.inspect(result)
    sdk_keys = sdk_reachable_keys(result)
    if sdk_keys != set(ARTIFACT_KEYS):
        print(
            "FAILED:IMP-0326-probe1 SDK keys incomplete "
            f"missing={sorted(set(ARTIFACT_KEYS) - sdk_keys)}"
        )
        return 1
    if inspection.keys() != frozenset(ARTIFACT_KEYS):
        print("FAILED:IMP-0326-probe1 inspect keys != ARTIFACT_KEYS")
        return 1

    parity = surface_parity(result)
    print(
        "sdk_minus_cli="
        + json.dumps(list(parity.sdk_minus_cli), sort_keys=True)
    )
    print(
        "cli_minus_sdk="
        + json.dumps(list(parity.cli_minus_sdk), sort_keys=True)
    )
    print("sdk_keys=" + json.dumps(list(parity.sdk_keys), sort_keys=True))
    print("cli_keys=" + json.dumps(list(parity.cli_keys), sort_keys=True))
    if not parity.equal:
        print("FAILED:IMP-0326-probe1 in-process parity unequal")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0326-p1-") as td:
        run_dir = Path(td)
        sdk.persist(result, run_dir)
        live = _cli_inspect(run_dir)
        live_keys = set(live)
        live_sdk_minus = sorted(sdk_keys - live_keys)
        live_cli_minus = sorted(live_keys - sdk_keys)
        print("live_sdk_minus_cli=" + json.dumps(live_sdk_minus))
        print("live_cli_minus_sdk=" + json.dumps(live_cli_minus))
        if live_sdk_minus or live_cli_minus:
            print("FAILED:IMP-0326-probe1 live CLI parity unequal")
            return 1
        if result.meta.run_id != "imp-0326-probe1":
            print("FAILED:IMP-0326-probe1 run_id mismatch")
            return 1
        if result.budgets.turns < 1 or result.votes.for_count < 1:
            print("FAILED:IMP-0326-probe1 empty council")
            return 1

    print(
        "e2e_sdk_council "
        f"run_id={result.meta.run_id} "
        f"status={result.decision.status.value} "
        f"rounds={result.stopping.rounds_completed} "
        f"turns={result.budgets.turns}"
    )
    print("typed_result=True")
    print("SUCCESS:IMP-0326-probe1 typed-results and SDK/CLI key parity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
