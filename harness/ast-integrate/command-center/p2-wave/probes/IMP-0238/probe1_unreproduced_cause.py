#!/usr/bin/env python3
"""Probe 1: unreproduced cause is rejected; reproduced cause is accepted.

Both-states control required by IMP-0238. The FLAGSHIP gate must fire on a
cause with no reproduction receipt and accept after an independent worker
has reproduced the planted increment failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parents[2] / "blueprints" / "engineering"
sys.path.insert(0, str(ENGINE))

from engine import (  # noqa: E402
    CAUSE_WITHOUT_REPRODUCTION,
    run_investigation,
    smoke_all,
)


def main() -> int:
    pack = smoke_all()
    if not pack.get("ok"):
        print("FAILED:IMP-0238-probe1 other blueprints did not smoke")
        print(json.dumps(pack, sort_keys=True, default=str)[:4000])
        return 1

    rejected = run_investigation("noop-increment is the cause", reproduce=False)
    accepted = run_investigation("noop-increment is the cause", reproduce=True)

    print(
        json.dumps(
            {
                "rejected": {
                    "status": rejected.status,
                    "reason": rejected.reason,
                    "executor_pid": rejected.executor_pid,
                    "observed_failure": rejected.observed_failure,
                },
                "accepted": {
                    "status": accepted.status,
                    "reason": accepted.reason,
                    "proposer_pid": accepted.proposer_pid,
                    "executor_pid": accepted.executor_pid,
                    "pids_differ": accepted.executor_pid != accepted.proposer_pid,
                    "observed_failure": accepted.observed_failure,
                },
                "blueprints_smoked": pack["registered"],
            },
            sort_keys=True,
        )
    )

    if rejected.status != "REJECTED" or rejected.reason != CAUSE_WITHOUT_REPRODUCTION:
        print(
            "FAILED:IMP-0238-probe1 unreproduced cause not rejected "
            f"status={rejected.status} reason={rejected.reason}"
        )
        return 1
    if accepted.status != "ACCEPTED":
        print(
            "FAILED:IMP-0238-probe1 reproduced cause not accepted "
            f"status={accepted.status} reason={accepted.reason}"
        )
        return 1
    if accepted.executor_pid is None or accepted.executor_pid == accepted.proposer_pid:
        print("FAILED:IMP-0238-probe1 accepted path did not use an independent executor")
        return 1
    if not accepted.observed_failure:
        print("FAILED:IMP-0238-probe1 accepted path did not observe the planted failure")
        return 1
    print("unreproduced_rejected=True reproduced_accepted=True both_states=True")
    print("SUCCESS:IMP-0238-probe1 unreproduced cause rejected, reproduced cause accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
