#!/usr/bin/env python3
"""Named probe 2: barrier must not wait past a unit's declared timeout.

Timestamps are read from the ledger. Both-states:
  isolated — barrier_wait_s <= declared timeout + slack, and strictly less
             than the planted hang duration (did not wait it out)
  coupled  — barrier_wait_s exceeds declared timeout (detector fires on the
             known-broken join-all)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    HANG_ID,
    HANG_S,
    SENTINEL,
    SLACK_S,
    TIMEOUT_S,
    assert_no_barrier_past_timeout,
    load_receipt,
    run_coupled_hang,
    run_isolated,
    summarize,
)


def main() -> int:
    try:
        doc = load_receipt()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAILED:IMP-0222-probe2 receipt {exc}")
        return 1

    isolated = run_isolated(hang=True)
    coupled = run_coupled_hang()
    si = summarize(isolated)
    sc = summarize(coupled)
    ok_iso, why_iso = assert_no_barrier_past_timeout(isolated, slack_s=SLACK_S)
    ok_cpl, why_cpl = assert_no_barrier_past_timeout(coupled, slack_s=SLACK_S)

    problems: list[str] = []
    if not ok_iso:
        problems.append(f"isolated exceeded declared timeout: {why_iso}")
    if ok_cpl:
        problems.append(
            f"coupled control was silent (barrier within timeout); detector dead: {why_cpl}"
        )
    if isolated.barrier_wait_s >= HANG_S - 0.15:
        problems.append(
            f"isolated barrier_wait_s={isolated.barrier_wait_s:.4f} waited out hang_s={HANG_S}"
        )
    if coupled.barrier_wait_s <= TIMEOUT_S:
        problems.append(
            f"coupled barrier_wait_s={coupled.barrier_wait_s:.4f} did not exceed timeout_s={TIMEOUT_S}"
        )
    if coupled.barrier_wait_s < HANG_S - 0.25:
        problems.append(
            f"coupled barrier_wait_s={coupled.barrier_wait_s:.4f} expected ~hang_s={HANG_S}"
        )

    hung = isolated.by_id().get(HANG_ID)
    if hung is None:
        problems.append("isolated ledger missing hung unit")
    else:
        if hung.duration_s > TIMEOUT_S + SLACK_S:
            problems.append(
                f"hung duration_s={hung.duration_s:.4f} > timeout+slack {TIMEOUT_S + SLACK_S}"
            )
        if hung.duration_s >= HANG_S - 0.15:
            problems.append(
                f"hung duration_s={hung.duration_s:.4f} matches hang_s not timeout"
            )

    late = [
        e.unit_id
        for e in isolated.entries
        if e.unit_id != HANG_ID and e.duration_s > TIMEOUT_S + SLACK_S
    ]
    if late:
        problems.append(f"siblings held past timeout: {late[:5]}")

    payload = {
        "unit_id": "IMP-0222",
        "probe": "probe2-barrier-timeout",
        "pass": not problems,
        "timeout_s": TIMEOUT_S,
        "hang_s": HANG_S,
        "slack_s": SLACK_S,
        "isolated_barrier_wait_s": isolated.barrier_wait_s,
        "coupled_barrier_wait_s": coupled.barrier_wait_s,
        "isolated_within_timeout": ok_iso,
        "coupled_exceeds_timeout": not ok_cpl,
        "hung_duration_s": None if hung is None else hung.duration_s,
        "isolated_summary": {
            k: si[k] for k in ("completed", "timeout", "timeout_typed", "barrier_wait_s")
        },
        "coupled_summary": {
            k: sc[k] for k in ("completed", "timeout", "timeout_typed", "barrier_wait_s")
        },
        "receipt_state": doc.get("state"),
        "sentinel_in_receipt": SENTINEL in json.dumps(doc),
        "problems": problems,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"isolated_wait={isolated.barrier_wait_s:.4f}s "
        f"coupled_wait={coupled.barrier_wait_s:.4f}s "
        f"timeout_s={TIMEOUT_S} hang_s={HANG_S}"
    )
    if problems:
        for p in problems:
            print(f"FAILED:IMP-0222-probe2 {p}")
        return 1
    print("SUCCESS:IMP-0222-probe2 barrier timestamps stay within declared timeout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
