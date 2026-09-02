#!/usr/bin/env python3
"""Red-proof: show that ``probe_capability.run_control()`` CAN return False.

A control that has never been observed to fail is indistinguishable from a
control that cannot fail.  This mutates the prober under ``run_control`` -- once
per state -- and requires the gate to go red every time.  It touches nothing on
disk and spawns nothing (``probe`` is replaced wholesale).

Run: ``python redproof_control.py``  ->  ``SUCCESS:redproof-control`` / exit 0.
"""

from __future__ import annotations

import os
import pathlib
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import probe_capability as pc  # noqa: E402  (path injection must precede)


def _row(**over: Any) -> dict[str, Any]:
    base = {
        "name": "x",
        "call_verified": False,
        "tool_count": None,
        "last_error": "boom",
        "elapsed_ms": 1,
    }
    base.update(over)
    return base


MUTATIONS = {
    # A prober that cannot reach the fixture at all.
    "good-broken": lambda state: _row(),
    # A prober that spawns fine but miscounts the fixture's surface: the exact-count
    # assertion is what catches an invented or static tool surface.
    "good-wrong-count": lambda state: (
        _row(call_verified=True, tool_count=99, last_error=None)
        if state == "GOOD"
        else _row()
    ),
    # A prober that reports success for a command that does not exist / speaks no
    # MCP -- i.e. one that measures process spawn instead of the handshake.
    "bad-reported-ok": lambda state: _row(
        call_verified=True,
        tool_count=1 if state == "GOOD" else 7,
        last_error=None,
    ),
}


def main() -> int:
    real = pc.probe
    baseline, _ = pc.run_control()
    if not baseline:
        print("FAILED:redproof-control baseline control is already red")
        return 1
    print("baseline control: GREEN (unmutated)")

    failures = []
    for label, factory in MUTATIONS.items():
        state_box: dict[str, str] = {}

        def fake(spec: dict[str, Any], timeout: float = 0.0, _f=factory, _b=state_box):
            return _f(_b.get("state", ""))

        def wrapped_run() -> bool:
            names = {
                "_control_good": "GOOD",
                "_control_missing": "MISSING",
                "_control_not_mcp": "NOT-MCP",
                "_control_shim": "SHIM",
            }

            def probe_stub(spec: dict[str, Any], timeout: float = 0.0):
                state_box["state"] = names.get(spec.get("name", ""), "")
                return fake(spec, timeout)

            pc.probe = probe_stub
            try:
                ok, _rows = pc.run_control()
            finally:
                pc.probe = real
            return ok

        went_red = not wrapped_run()
        print(f"mutation {label:18} -> control red? {went_red}")
        if not went_red:
            failures.append(label)

    # Real-code mutation (not a stub): revert the PATHEXT fix and require the SHIM
    # state to catch it.  This is the both-states proof for the actual bug that made
    # the first sweep report five working servers as broken.
    # NB: run_control() returns a (ok, rows) TUPLE.  The first version of this line
    # was `not pc.run_control()`, and a non-empty tuple is always truthy, so it
    # reported "mutation survived" for a mutation the control was in fact catching.
    # Caught by measuring run_control() directly and getting the opposite answer --
    # a self-contradicting output is a detector failure, not a finding.
    #
    # WINDOWS-ONLY.  ``run_control`` skips the SHIM state on POSIX (no PATHEXT, no ``.cmd``),
    # so reverting the fix there changes nothing observable and the mutation would be scored
    # as a SURVIVOR -- a red gate reporting a defect that cannot exist on the host.  Measured
    # on Ubuntu 24.04 before this branch: the baseline itself was already red.  Skipping it is
    # only safe because ``pathext_applicable`` is asserted below, so the mutation cannot go
    # missing on Windows without the count check firing.
    pathext_applicable = os.name == "nt"
    if pathext_applicable:
        pc.RESOLVE_SHIMS = False
        try:
            shim_ok, _shim_rows = pc.run_control()
        finally:
            pc.RESOLVE_SHIMS = True
        shim_red = not shim_ok
        print(f"mutation {'no-pathext-resolve':18} -> control red? {shim_red}")
        if not shim_red:
            failures.append("no-pathext-resolve")
    else:
        print(
            f"mutation {'no-pathext-resolve':18} -> SKIPPED "
            "(posix: SHIM state unobservable, mutation has no effect to detect)"
        )

    total = len(MUTATIONS) + (1 if pathext_applicable else 0)
    expected_total = 4 if pathext_applicable else 3
    if total != expected_total:
        print(
            f"FAILED:redproof-control ran {total} mutations, expected {expected_total}"
        )
        return 1
    if failures:
        print(f"FAILED:redproof-control survivors={failures}")
        return 1
    print(f"SUCCESS:redproof-control {total}/{total} mutations caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
