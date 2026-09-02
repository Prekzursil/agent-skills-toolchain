#!/usr/bin/env python3
"""IMP-0404 probe 1: fail-open with forced exception; session smoke; both-states.

GOOD: repo hooks, router forced to raise, every event exits 0, hook log has
zero exit-2 rows, tools are not denied.
BAD: a leaky twin that converts the same raise into sys.exit(2) — the
detector must fire on that twin.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import session_lib as S  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0404-probe1 {msg}")
    return 1


def main() -> int:
    S.require_receipt()
    with tempfile.TemporaryDirectory(prefix="imp0404-p1-") as tmp:
        tmp_path = Path(tmp)
        log_path = tmp_path / "hook.jsonl"
        smoke = S.smoke_session(fault="raise", log_path=log_path)

        leaky = S.leaky_twin_exit()
        fired_on_bad = leaky == 2
        silent_on_good = (
            smoke["all_exit_zero"] and smoke["zero_exit2_log"] and smoke["no_deny"]
        )

        happy_log = tmp_path / "happy.jsonl"
        happy = S.smoke_session(fault="", log_path=happy_log)
        happy_ok = happy["all_exit_zero"] and happy["no_deny"]
        injected = False
        for r in happy["runs"]:
            hso = r["payload"].get("hookSpecificOutput") or {}
            ctx = str(hso.get("additionalContext") or "")
            if "cap.router-audit" in ctx or "additive context" in ctx:
                injected = True
                break

        out = {
            "probe": "probe1-fail-open",
            "unit_id": "IMP-0404",
            "forced_exception": "IMP0404_ROUTER_FAULT=raise",
            "n_events": smoke["n_events"],
            "exit_codes": smoke["exit_codes"],
            "log_exits": smoke["log_exits"],
            "all_exit_zero": smoke["all_exit_zero"],
            "zero_exit2_log": smoke["zero_exit2_log"],
            "no_deny": smoke["no_deny"],
            "fail_open_payloads": [
                bool((r["payload"] or {}).get("failOpen")) for r in smoke["runs"]
            ],
            "leaky_twin_exit": leaky,
            "fired_on_bad": fired_on_bad,
            "silent_on_good": silent_on_good,
            "happy_path_exit_zero": happy_ok,
            "happy_path_injected": injected,
            "pass": bool(
                silent_on_good
                and fired_on_bad
                and happy_ok
                and injected
                and smoke["n_events"] >= 4
            ),
        }
        print(json.dumps(out, sort_keys=True))
        print(
            f"fail_open={silent_on_good} leaky_twin={leaky} "
            f"exit_codes={smoke['exit_codes']} log_exits={smoke['log_exits']} "
            f"injected={injected}"
        )
        if not out["pass"]:
            return fail("forced-exception session did not fail-open with both-states")
        print(
            "SUCCESS:IMP-0404-probe1 fail-open on forced exception; "
            "session smoke exit 0; leaky twin exits 2"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
