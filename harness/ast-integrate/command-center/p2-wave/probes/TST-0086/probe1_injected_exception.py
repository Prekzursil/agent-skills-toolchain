#!/usr/bin/env python3
"""Probe 1: inject an exception at each live hook entry; session must still exit 0.

Live subprocesses against agent-self/config/settings.json Python hooks and
hooks/_dispatch/dispatch.py in-process checks. Bare (no fail-open) inject must
be non-zero so the wrapped zero is not silent-in-both-states.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0086.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0086-probe1 {msg}")
    return 1


def as_int(value, default=None):
    if value is None:
        return default
    return int(value)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:TST-0086" not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if doc.get("kind") != "detector-control":
        return fail("kind is not detector-control")

    live = E.inject_each_hook()
    if not live.get("pass"):
        return fail("live inject-each-hook did not pass")
    expected = [h["id"] for h in S.registered_hooks()]
    if int(live.get("hook_count") or 0) != len(expected):
        return fail("hook count mismatch vs live registration")
    if as_int(live.get("unwrapped_exit_code")) == 0:
        return fail("unwrapped inject was silent (exit 0)")
    for row in live["observations"]:
        print(
            f"hook {row['id']} wrap_exit={row['exit_code']} "
            f"process_exit={row['process_exit']} "
            f"unwrapped={row['unwrapped_exit_code']} "
            f"continued={row['session_continued']} "
            f"body_fired={row['hook_body_fired']} "
            f"later={row['later_hooks_ran']}"
        )
        if as_int(row["exit_code"]) != 0:
            return fail(f"{row['id']} wrapped session exit {row['exit_code']}")
        if as_int(row["unwrapped_exit_code"]) == 0:
            return fail(f"{row['id']} unwrapped inject was silent (exit 0)")
        if row.get("hook_body_fired"):
            return fail(f"{row['id']} body ran; inject missed entry")
        if not row.get("session_continued"):
            return fail(f"{row['id']} session did not continue")

    rec_obs = {
        r.get("id"): r
        for r in (doc.get("observations") or [])
        if isinstance(r, dict) and str(r.get("id") or "").startswith("hook.")
    }
    for row in live["observations"]:
        got = rec_obs.get(row["id"])
        if not got:
            return fail(f"artifact missing observation {row['id']}")
        if as_int(got.get("exit_code")) != 0:
            return fail(f"artifact {row['id']} exit_code not 0")
        if str(got.get("outcome") or "") != "fail-open":
            return fail(f"artifact {row['id']} outcome {got.get('outcome')}")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    t1 = tests.get("test_injected_exception_exits_zero_for_every_hook")
    if not t1 or t1.get("result") != "PASS":
        return fail("artifact test_injected_exception_exits_zero_for_every_hook not PASS")

    out = {
        "probe": "probe1-injected-exception",
        "unit_id": "TST-0086",
        "hook_count": live["hook_count"],
        "all_wrapped_exit_zero": True,
        "unwrapped_inject_nonzero": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:TST-0086-probe1 injected exception exits 0 for every hook")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
