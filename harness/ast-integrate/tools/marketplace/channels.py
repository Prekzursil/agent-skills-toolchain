"""Channel pin matrix: a client pinned to a channel never sees others (IMP-0071)."""
from __future__ import annotations

from typing import Any

CONDITION_13_INLINE = (
    "Condition 13 is unsatisfiable as written under PR-ONLY: a promotion "
    "cannot both land in the live index and remain a pull request."
)
CONDITION_13_STATUS = "unsatisfiable-as-written"
CONDITION_13_TEXT = CONDITION_13_INLINE
RELEASE_MODE = "PR-ONLY"

PIN_MATRIX = (
    ("pin-stable", "stable", "1.0.0", True),
    ("pin-stable-hide-beta", "stable", "1.1.0-beta.1", False),
    ("pin-stable-hide-canary", "stable", "1.2.0-canary.1", False),
    ("pin-beta", "beta", "1.1.0-beta.1", True),
    ("pin-beta-hide-canary", "beta", "1.2.0-canary.1", False),
    ("pin-beta-stable-ok", "beta", "1.0.0", True),
    ("pin-canary", "canary", "1.2.0-canary.1", True),
    ("pin-canary-beta-ok", "canary", "1.1.0-beta.1", True),
    ("pin-canary-stable-ok", "canary", "1.0.0", True),
    ("cross-channel-refuse", "stable", "1.2.0-canary.1", False),
)

_CHANNEL_RANK = {"stable": 0, "beta": 1, "canary": 2}


def _visible(pin: str, version: str) -> bool:
    if "canary" in version:
        ch = "canary"
    elif "beta" in version:
        ch = "beta"
    else:
        ch = "stable"
    return _CHANNEL_RANK[ch] <= _CHANNEL_RANK[pin]


def resolve(pin: str, version: str) -> bool:
    return _visible(pin, version)


def run_pin_matrix() -> dict[str, Any]:
    results = []
    failed = []
    for case_id, pin, version, expect in PIN_MATRIX:
        got = resolve(pin, version)
        row = {
            "id": case_id,
            "pin": pin,
            "version": version,
            "expected": expect,
            "got": got,
            "ok": got is expect,
        }
        results.append(row)
        if not row["ok"]:
            failed.append(case_id)
    return {
        "cases": len(PIN_MATRIX),
        "passed": len(PIN_MATRIX) - len(failed),
        "failed": failed,
        "pass": not failed,
        "results": results,
    }
