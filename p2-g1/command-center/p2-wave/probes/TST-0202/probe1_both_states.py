#!/usr/bin/env python3
"""TST-0202 probe 1: both-states control on a DIRECT (non-junction) path.

A direct path whose RESOLVED length equals the alias scenario's resolved
length must behave identically: over budget -> PathBudgetExceeded with zero
residue; under budget -> writes silently with the resolved length recorded.
Independent signal: os.path.realpath in a fresh interpreter resolves the same
path to the same measured length.
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scenario import SCENARIO, build, teardown  # noqa: E402


def main() -> int:
    info = build()
    from artifact_writer import (  # noqa: E402
        PathBudgetExceeded,
        WINDOWS_MAX_PATH,
        resolved_length,
        write_artifact,
    )

    deep = info["deep"]
    over_path = deep / "over.bin"
    under_path = SCENARIO / "short-direct.bin"
    over_refused = None
    residue_over = -1
    try:
        write_artifact(over_path, b"x")
        over_refused = False
    except PathBudgetExceeded as exc:
        over_refused = True
        residue_over = int(exc.check["residue_bytes"])
    under_ok = False
    under_check = {}
    try:
        under_check = write_artifact(under_path, b"under-budget-payload")
        under_ok = under_check["measure"] == "resolved" and under_check["wrote"] is True
    except PathBudgetExceeded:
        under_ok = False

    code = (
        "import os, json; print(json.dumps(len(os.path.realpath("
        "r\"%s\"))))" % str(deep)
    )
    second = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=120)
    independent_len = -1
    try:
        independent_len = int(second.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        independent_len = -1

    checks = {
        "over_budget_direct_refused": over_refused is True,
        "zero_residue_on_refusal": residue_over == 0,
        "under_budget_direct_writes_resolved": under_ok,
        "independent_realtime_agrees": independent_len == resolved_length(deep),
        "scenario_over_budget": info["over_budget"] is True,
        "both_states_same_behavior": (over_refused is True) and under_ok,
    }
    out = {
        "probe": "probe1_both_states",
        "unit": "TST-0202",
        "alias_len": info["alias_len"],
        "resolved_len": info["resolved_len"],
        "independent_len": independent_len,
        "budget": WINDOWS_MAX_PATH,
        "residue_over": residue_over,
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe1_both_states.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    teardown()
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
