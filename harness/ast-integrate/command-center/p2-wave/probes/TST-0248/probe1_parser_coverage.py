#!/usr/bin/env python3
"""Probe 1: every parser command, not docs, run with stdin=DEVNULL under hang bound."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402


def main() -> int:
    live = H.measure_cli()
    print(json.dumps({k: v for k, v in live.items() if k != "invocations"}, sort_keys=True))
    failing = [r for r in live["invocations"] if not r["ok"]]
    for row in live["invocations"]:
        print(
            f"{row['id']} rc={row['returncode']} elapsed={row['elapsed_s']} "
            f"timed_out={row['timed_out']} ok={row['ok']} reason={row['reason']}"
        )
    if live["missing_from_runs"]:
        print("FAILED:TST-0248-probe1 parser command not run:", live["missing_from_runs"])
        return 1
    if live["command_count"] < 1:
        print("FAILED:TST-0248-probe1 empty parser enumeration")
        return 1
    if live["any_timed_out"] or live["max_elapsed_s"] >= H.HANG_BOUND_S:
        print("FAILED:TST-0248-probe1 hang bound breached")
        return 1
    if failing:
        print("FAILED:TST-0248-probe1 invocations failed:", [r["id"] for r in failing])
        return 1
    if not live["all_ok"]:
        print("FAILED:TST-0248-probe1 coverage incomplete")
        return 1
    print(
        f"commands={live['commands']} n={live['command_count']} "
        f"max_elapsed_s={live['max_elapsed_s']} stdin=DEVNULL"
    )
    print("SUCCESS:TST-0248-probe1 parser-enumerated null-stdin coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
