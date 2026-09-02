#!/usr/bin/env python3
"""Probe 2: simulator terminal-state sweep + required-output completeness.

Independent of probe 1: re-runs the deterministic simulator and checks
timeout-is-FAILED plus a missing-output mutant.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from sweep import sweep  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0293.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0293-probe2 {msg}")
    return 1


def main() -> int:
    live = sweep(seed=0)
    slim = {k: live[k] for k in live if k not in {"runs", "table"}}
    print(json.dumps(slim, sort_keys=True, default=str))
    if live["n"] != 64:
        return fail(f"n={live['n']}")
    if not live["all_terminal_done"]:
        bad = [r for r in live["table"] if r["terminal_state"] != "DONE"]
        return fail(f"non-terminal {bad[:5]}")
    if not live["all_outputs_complete"]:
        bad = [r for r in live["table"] if r["outputs_missing"]]
        return fail(f"incomplete {bad[:3]}")
    if live["distinctness_collisions"]:
        return fail(f"distinctness {live['distinctness_collisions'][:2]}")
    if not live["timeout_control"]["fired"]:
        return fail("timeout control did not FAIL")
    if not live["missing_output_control"]["fired"]:
        return fail("missing-output mutant still complete")
    if live["named_in_table_missing"]:
        return fail(f"named not in table {live['named_in_table_missing']}")
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        table = doc.get("per_preset_table") or []
        if len(table) != 64:
            return fail(f"receipt table {len(table)}")
        timeouts = [r for r in table if r.get("terminal_state") == "TIMEOUT"]
        if timeouts:
            return fail(f"receipt hides timeout as pass? {timeouts[:1]}")
        failed_as_timeout = [
            r for r in table if r.get("terminal_state") == "TIMEOUT" and r.get("row_result") != "FAILED"
        ]
        if failed_as_timeout:
            return fail("timeout not FAILED")
    print("SUCCESS:TST-0293-probe2 simulator sweep completeness and timeout-is-FAILED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
