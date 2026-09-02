#!/usr/bin/env python3
"""Probe 1: detector control — splice-eval MUST create the canary; the pipeline must not.

Catalog tests_required: deliberately eval one parameter and confirm the canary
marker appears, proving the probe can detect substitution. Then the same
payload through every sink: canary absent AND recorded bytes equal the input.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.shell.param_pipeline import (  # noqa: E402
    SINKS,
    cmd_percent_expand,
    run_pipeline,
    tools_ok,
    unsafe_splice_eval,
)


def main() -> int:
    tools = tools_ok()
    if not (tools["bash_exists"] and tools["printf_exists"] and tools["cat_exists"]):
        print(json.dumps({"pass": False, "tools": tools}, indent=2, sort_keys=True))
        print("FAILED:TST-0193-probe1 missing bash/printf/cat")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="tst0193-p1-"))
    canary = tmp / "CANARY.marker"
    payload_dollar = f"$(touch {canary})"
    payload_tick = f"`touch {canary}`"

    # --- detector: splice into bash MUST create the marker ---
    canary.unlink(missing_ok=True)
    unsafe_splice_eval(payload_dollar, cwd=str(tmp))
    dollar_fired = canary.is_file()
    canary.unlink(missing_ok=True)
    unsafe_splice_eval(payload_tick, cwd=str(tmp))
    tick_fired = canary.is_file()
    canary.unlink(missing_ok=True)

    # %VAR% detector: cmd-style expander changes the value; pipeline must not.
    fake_env = {"PATH": "/should-not-leak-into-sink", "TST0193_CANARY": str(canary)}
    pct_payload = "%PATH%"
    pct_expanded = cmd_percent_expand(pct_payload, fake_env)
    pct_detector_fires = pct_expanded == fake_env["PATH"] and pct_expanded != pct_payload

    # --- production pipeline: same payloads, canary stays absent, literals match ---
    dollar_rows = run_pipeline(payload_dollar, workdir=tmp / "pipe-dollar", canary=canary)
    dollar_canary = canary.is_file()
    dollar_literal = all(r.literal for r in dollar_rows)

    tick_rows = run_pipeline(payload_tick, workdir=tmp / "pipe-tick", canary=canary)
    tick_canary = canary.is_file()
    tick_literal = all(r.literal for r in tick_rows)

    pct_rows = run_pipeline(pct_payload, workdir=tmp / "pipe-pct", canary=canary)
    pct_canary = canary.is_file()
    pct_literal = all(r.literal for r in pct_rows)

    ok = (
        dollar_fired
        and tick_fired
        and pct_detector_fires
        and not dollar_canary
        and not tick_canary
        and not pct_canary
        and dollar_literal
        and tick_literal
        and pct_literal
        and len(dollar_rows) == len(SINKS)
    )
    report = {
        "probe": "probe1-detector-control",
        "unit_id": "TST-0193",
        "pass": ok,
        "tools": tools,
        "detector": {
            "dollar_paren_splice_created_canary": dollar_fired,
            "backtick_splice_created_canary": tick_fired,
            "percent_expand_changes_value": pct_detector_fires,
            "percent_expanded": pct_expanded,
            "percent_original": pct_payload,
        },
        "pipeline": {
            "sinks": list(SINKS),
            "dollar_canary_present": dollar_canary,
            "backtick_canary_present": tick_canary,
            "percent_canary_present": pct_canary,
            "dollar_literal_all_sinks": dollar_literal,
            "backtick_literal_all_sinks": tick_literal,
            "percent_literal_all_sinks": pct_literal,
            "dollar_received": {r.sink: r.received for r in dollar_rows},
            "backtick_received": {r.sink: r.received for r in tick_rows},
            "percent_received": {r.sink: r.received for r in pct_rows},
        },
        "canary_path": str(canary),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    shutil.rmtree(tmp, ignore_errors=True)
    if not ok:
        print("FAILED:TST-0193-probe1 detector did not discriminate splice vs pipeline")
        return 1
    print(
        "SUCCESS:TST-0193-probe1 splice-eval creates canary; "
        "pipeline keeps it absent and records literals"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
