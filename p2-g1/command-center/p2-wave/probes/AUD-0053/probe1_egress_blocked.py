#!/usr/bin/env python3
"""Probe 1: suite under egress block; record tests whose outcome changes.

Both-states control: a deliberate fetch must raise EgressBlocked inside the
block, and must not raise EgressBlocked when the hook is in trace mode.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import compact, run_census  # noqa: E402

CONNECT = (
    "command-center/p2-wave/probes/AUD-0053/controls/test_connect_attempt.py"
)
HERMETIC = (
    "command-center/p2-wave/probes/AUD-0053/controls/test_hermetic_noop.py"
)
LOOPBACK = (
    "command-center/p2-wave/probes/AUD-0053/controls/test_loopback_touch.py"
)
GETPIP = (
    "command-center/p2-wave/probes/AUD-0053/controls/test_deliberate_fetch.py"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0053-probe1 {msg}")
    return 1


def row_for(census: dict, rel: str) -> dict | None:
    for row in census.get("rows") or []:
        if row.get("repo_path") == rel:
            return row
    return None


def main() -> int:
    census = run_census(include_product=True)
    control = census["control"]
    payload = {
        "pass": False,
        "probe": "probe1-egress-blocked",
        "unit_id": "AUD-0053",
        "summary": compact(census),
        "control": {
            k: control.get(k)
            for k in (
                "pass",
                "blocked_raises_egress_blocked",
                "unblocked_raises_egress_blocked",
                "unblocked_result",
                "unblocked_named_control_host",
                "blocked_exception_type",
            )
        },
    }
    if not control.get("pass"):
        print(json.dumps(payload, sort_keys=True))
        return fail("both-states block control did not prove the hook")

    connect = row_for(census, CONNECT)
    hermetic = row_for(census, HERMETIC)
    loopback = row_for(census, LOOPBACK)
    getpip = row_for(census, GETPIP)
    if connect is None or hermetic is None or loopback is None or getpip is None:
        print(json.dumps(payload, sort_keys=True))
        return fail("planted controls missing from census rows")

    if not connect["depends_on_egress"]:
        print(json.dumps(payload, sort_keys=True))
        return fail(
            f"connect-attempt did not flip: blocked={connect['blocked_outcome']} "
            f"unblocked={connect['unblocked_outcome']}"
        )
    if connect["blocked_outcome"] != "FAIL" or connect["unblocked_outcome"] != "PASS":
        print(json.dumps(payload, sort_keys=True))
        return fail("connect-attempt must be FAIL blocked / PASS unblocked")
    if hermetic["classification"] != "hermetic" or hermetic["depends_on_egress"]:
        print(json.dumps(payload, sort_keys=True))
        return fail(f"hermetic control misclassified {hermetic['classification']}")
    if loopback["depends_on_egress"] or loopback["touches_egress"]:
        print(json.dumps(payload, sort_keys=True))
        return fail("loopback was treated as egress")
    if not getpip["touches_egress"] and not getpip["depends_on_egress"]:
        print(json.dumps(payload, sort_keys=True))
        return fail("get-pip planted control was invisible to the block detector")

    payload["planted"] = {
        "connect_attempt": {
            k: connect[k]
            for k in ("classification", "depends_on_egress", "blocked_outcome", "unblocked_outcome")
        },
        "hermetic": {"classification": hermetic["classification"]},
        "loopback": {
            "classification": loopback["classification"],
            "touches_egress": loopback["touches_egress"],
            "loopback_hosts": loopback.get("loopback_hosts"),
        },
        "get_pip": {
            "classification": getpip["classification"],
            "touches_egress": getpip["touches_egress"],
            "depends_on_egress": getpip["depends_on_egress"],
            "egress_hosts": getpip.get("egress_hosts"),
        },
    }
    payload["pass"] = True
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:AUD-0053-probe1 "
        f"depend={census['n_depend']} touch={census['n_touch']} "
        f"hermetic={census['n_hermetic']} "
        f"control=EgressBlocked-then-not files={census['n_files_run']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
