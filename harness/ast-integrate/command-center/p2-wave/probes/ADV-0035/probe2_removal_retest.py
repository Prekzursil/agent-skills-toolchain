#!/usr/bin/env python3
"""Probe 2: removal-and-retest plus live attempted-call observation.

Mechanically different from probe 1 (does not consult historical traces for
the unused/unexercised distinction). A permission whose removal changes
nothing is unused; a permission whose removal fails tests was unexercised.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import reconcile as R  # noqa: E402

from plugin.permission_diff import canonicalize  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:ADV-0035-probe2 {msg}")
    return 1


def _row(retests: list[dict], cid: str, perm: str) -> dict | None:
    want = canonicalize(perm)
    for r in retests:
        if r["id"] == cid and r["removed"] == want:
            return r
    return None


def main() -> int:
    pack = R.load_fixture_pack()
    analysis = R.analyze_fixtures(pack)
    bash = canonicalize("Bash")
    write = canonicalize("Write")
    read = canonicalize("Read")
    grep = canonicalize("Grep")

    retests = analysis["retests"]
    lives = {row["id"]: row for row in analysis["live_attempts"]}

    over_bash = _row(retests, "fx-overdeclare-unused", bash)
    unex_write = _row(retests, "fx-unexercised-needed", write)
    honest_read = _row(retests, "fx-honest", read)
    honest_grep = _row(retests, "fx-honest", grep)
    thin_bash = _row(retests, "fx-thin-trace", bash)
    under_live = lives["fx-underdeclare"]
    honest_live = lives["fx-honest"]

    payload = {
        "instrument": "removal-retest+live-attempts",
        "retests": retests,
        "live_attempts": analysis["live_attempts"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    if over_bash is None or not over_bash["confirmed_unused"]:
        return _fail("removing planted unused Bash must leave tests passing")
    if unex_write is None or not unex_write["needed_but_unexercised"]:
        return _fail("removing unexercised Write must fail tests")
    if honest_read is None or not honest_read["needed_but_unexercised"]:
        return _fail("removing Read from honest fixture must fail tests")
    if honest_grep is None or not honest_grep["needed_but_unexercised"]:
        return _fail("removing Grep from honest fixture must fail tests")
    if write not in under_live["under_declared_live"]:
        return _fail("live execution must still attempt undeclared Write")
    if honest_live["under_declared_live"]:
        return _fail("honest live execution must not attempt undeclared perms")

    # Thin-trace Bash is unused by tests, so a naive retest would "confirm"
    # it. Probe 2 records that fact but does not override the coverage guard.
    if thin_bash is None or not thin_bash["confirmed_unused"]:
        return _fail("thin-trace Bash naive retest should still pass (guard lives in probe 1)")

    print("SUCCESS:ADV-0035-probe2 removal-retest and live attempts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
