#!/usr/bin/env python3
"""Probe 1: an expired live result cannot satisfy a gate.

Both-states in one process: back-date an advisory-db PASS past its TTL
(must be NOT-CHECKED) and keep a fresh twin (must still be PASS).
Injected clock; no wall clock.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from bench.expire import cite_as_current, dashboard, gate_accepts  # noqa: E402
from bench.oracles import case_by_id, execute_case  # noqa: E402
from bench.ttl import ttl_for  # noqa: E402

NOW = datetime(2026, 8, 24, 18, 0, 0, tzinfo=timezone.utc)


def main() -> int:
    ttl = ttl_for("advisory-db")
    if ttl is None:
        print("FAILED:TST-0303-probe1 advisory-db TTL is never-expire")
        return 1
    case = case_by_id("advisory-nvd")
    live = execute_case(case, captured_at=NOW, result_id="adv-fresh")
    if live.observed_class != "advisory-db":
        print(f"FAILED:TST-0303-probe1 observed {live.observed_class}")
        return 1
    expired = execute_case(
        case, captured_at=NOW - timedelta(seconds=ttl + 1), result_id="adv-expired"
    )
    expired.verdict = "PASS"
    live.verdict = "PASS"
    bad = gate_accepts(expired, NOW)
    good = gate_accepts(live, NOW)
    cite_bad = cite_as_current(expired, NOW)
    dash = dashboard([expired, live], NOW)
    ages = [g.get("age_seconds") for g in dash["greens"]]
    payload = {
        "expired_accepted": bad["accepted"],
        "expired_as": bad["as"],
        "expired_reason": bad["reason"],
        "fresh_accepted": good["accepted"],
        "fresh_as": good["as"],
        "cite_status": cite_bad.status,
        "ttl_seconds": ttl,
        "expired_count": dash["expired_count"],
        "green_ages": ages,
        "observed_class": live.observed_class,
        "pass": (
            bad["accepted"] is False
            and bad["as"] == "NOT-CHECKED"
            and good["accepted"] is True
            and good["as"] == "PASS"
            and cite_bad.status == "EXPIRED-NOT-CHECKED"
            and dash["expired_count"] == 1
            and all(a is not None for a in ages)
        ),
        "probe": "probe1-expired-cannot-gate",
        "unit_id": "TST-0303",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"expired_accepted={bad['accepted']} as={bad['as']} "
        f"fresh_accepted={good['accepted']} expired_count={dash['expired_count']}"
    )
    if not payload["pass"]:
        print("FAILED:TST-0303-probe1 expired result still satisfied the gate")
        return 1
    print("SUCCESS:TST-0303-probe1 expired live result cannot satisfy a gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
