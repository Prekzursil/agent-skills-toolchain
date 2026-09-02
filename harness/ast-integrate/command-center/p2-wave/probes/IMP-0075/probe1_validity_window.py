#!/usr/bin/env python3
"""Named probe 1: expired key is rejected; in-window key is accepted in the same run."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.publisher import (  # noqa: E402
    REASON_ACCEPTED,
    REASON_EXPIRED,
    REASON_NOT_YET,
    REASON_UNKNOWN_PUBLISHER,
    load_registry,
    verify_publisher_key,
)

AT = datetime(2026, 8, 24, 18, 0, 0, tzinfo=timezone.utc)
FIXTURE = REPO / "tools" / "marketplace" / "fixtures" / "publishers.json"
PID = "owner.ast-integrate"


def main() -> int:
    if not FIXTURE.is_file():
        print("FAILED:IMP-0075-probe1 fixture missing")
        return 1
    reg = load_registry(FIXTURE)
    expired = verify_publisher_key(reg, PID, "k-expired", at=AT)
    current = verify_publisher_key(reg, PID, "k-current", at=AT)
    future = verify_publisher_key(reg, PID, "k-future", at=AT)
    unknown = verify_publisher_key(reg, "no.such.publisher", "k-current", at=AT)
    pub = reg.get(PID)
    usable = [k.key_id for k in pub.usable_keys(AT)] if pub else []

    report = {
        "probe": "probe1-validity-window",
        "unit_id": "IMP-0075",
        "at": AT.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expired": {"accepted": expired.accepted, "reason": expired.reason},
        "in_window": {"accepted": current.accepted, "reason": current.reason},
        "not_yet_valid": {"accepted": future.accepted, "reason": future.reason},
        "unknown_publisher": {"accepted": unknown.accepted, "reason": unknown.reason},
        "usable_key_ids": usable,
        "same_run_negative_control": current.accepted and not expired.accepted,
        "pass": False,
    }
    ok = (
        expired.accepted is False
        and expired.reason == REASON_EXPIRED
        and current.accepted is True
        and current.reason == REASON_ACCEPTED
        and future.accepted is False
        and future.reason == REASON_NOT_YET
        and unknown.accepted is False
        and unknown.reason == REASON_UNKNOWN_PUBLISHER
        and usable == ["k-current"]
    )
    report["pass"] = ok
    print(json.dumps(report, sort_keys=True))
    print(
        f"expired_rejected={not expired.accepted} in_window_accepted={current.accepted} "
        f"usable={usable} unknown_rejected={not unknown.accepted}"
    )
    if not ok:
        print("FAILED:IMP-0075-probe1 validity window")
        return 1
    print("SUCCESS:IMP-0075-probe1 expired rejected and in-window accepted in one run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
