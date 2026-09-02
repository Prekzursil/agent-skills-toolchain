#!/usr/bin/env python3
"""Probe 2: negative control — hide one CLI artifact and assert parity FAILS.

Independent of probe1's conclusion text. Re-runs the SDK, checks the good
state is equal, then omits `votes` from the CLI inspect payload.
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
    CouncilSDK,
    sdk_reachable_keys,
    surface_parity,
)

SDK_CLI = REPO / "tools" / "council" / "sdk.py"
HIDDEN = "votes"


def _cli_inspect(run_dir: Path, hide: list[str] | None = None) -> dict:
    cmd = [
        sys.executable,
        "-B",
        str(SDK_CLI),
        "inspect",
        "--run-dir",
        str(run_dir),
    ]
    for key in hide or []:
        cmd.extend(["--hide", key])
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={
            **{k: v for k, v in __import__("os").environ.items()},
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"FAILED:IMP-0326-probe2 cli inspect rc={proc.returncode} "
            f"stderr={proc.stderr[-500:]}"
        )
    data = json.loads(proc.stdout)
    if not isinstance(data, dict):
        raise SystemExit("FAILED:IMP-0326-probe2 CLI inspect did not emit an object")
    return data


def main() -> int:
    sdk = CouncilSDK()
    spec = sdk.build_fixture()
    result = sdk.execute(spec, run_id="imp-0326-probe2")
    good = surface_parity(result)
    print(
        "good_sdk_minus_cli="
        + json.dumps(list(good.sdk_minus_cli))
    )
    print(
        "good_cli_minus_sdk="
        + json.dumps(list(good.cli_minus_sdk))
    )
    if not good.equal:
        print("FAILED:IMP-0326-probe2 good-state parity already unequal")
        return 1

    hidden = surface_parity(result, hide_from_cli=[HIDDEN])
    print(
        "hidden_sdk_minus_cli="
        + json.dumps(list(hidden.sdk_minus_cli))
    )
    print(
        "hidden_cli_minus_sdk="
        + json.dumps(list(hidden.cli_minus_sdk))
    )
    if hidden.equal:
        print("FAILED:IMP-0326-probe2 hiding CLI key did not break parity")
        return 1
    if list(hidden.sdk_minus_cli) != [HIDDEN]:
        print(
            "FAILED:IMP-0326-probe2 expected sdk-cli "
            f"== [{HIDDEN!r}] got {list(hidden.sdk_minus_cli)}"
        )
        return 1
    if list(hidden.cli_minus_sdk) != []:
        print("FAILED:IMP-0326-probe2 cli-sdk not empty after hide")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0326-p2-") as td:
        run_dir = Path(td)
        sdk.persist(result, run_dir)
        live_good = set(_cli_inspect(run_dir))
        live_bad = set(_cli_inspect(run_dir, hide=[HIDDEN]))
        sdk_keys = sdk_reachable_keys(result)
        if live_good != sdk_keys:
            print(
                "FAILED:IMP-0326-probe2 live good CLI keys != SDK "
                f"sdk_minus={sorted(sdk_keys - live_good)} "
                f"cli_minus={sorted(live_good - sdk_keys)}"
            )
            return 1
        live_sdk_minus = sorted(sdk_keys - live_bad)
        live_cli_minus = sorted(live_bad - sdk_keys)
        print("live_hidden_sdk_minus_cli=" + json.dumps(live_sdk_minus))
        print("live_hidden_cli_minus_sdk=" + json.dumps(live_cli_minus))
        if live_sdk_minus != [HIDDEN] or live_cli_minus:
            print("FAILED:IMP-0326-probe2 live hide did not isolate votes")
            return 1

    print(f"negative_control_hide={HIDDEN} parity_fails=True good_state_equal=True")
    print("SUCCESS:IMP-0326-probe2 hide-one-CLI-artifact parity FAILS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
