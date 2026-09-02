#!/usr/bin/env python3
"""Probe 1: recorded transcript reproduced byte-identically twice.

Mechanisms: live two-run SHA256 identity, and a disk-recorded recount snapshot.
A one-vote script perturbation must change the digest (not a cached constant).
EmptyRuntime two-run identity is shown and must NOT be treated as a pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402


def main() -> int:
    row = H.measure_probe1()
    print(json.dumps(row, sort_keys=True))
    print(
        "two_run_identical={two_run_identical} live_vs_recorded={live_vs_recorded} "
        "recount_vs_recorded={recount_vs_recorded} events={event_count} "
        "kinds={kinds} winner={winner}".format(**row)
    )
    print(
        "perturbed_diverges={perturbed_diverges} seed_changed={seed_changed_on_vote_flip} "
        "empty_identical={empty_runtime_identical} empty_ok={empty_runtime_ok}".format(
            **row
        )
    )
    if not row["ok"]:
        print("FAILED:CNL-0117-probe1 byte-identical recorded transcript")
        return 1
    print("SUCCESS:CNL-0117-probe1 recorded transcript byte-identical twice")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
