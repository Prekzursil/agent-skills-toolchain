#!/usr/bin/env python3
"""Probe 2: independent re-measure of the spawn failure length.

Uses a different filler byte and fork+execv (not subprocess.Popen) so the
second curve is not a same-fingerprint replay of probe 1. Threshold must
still sit strictly below the re-measured first-fail length.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "plugin"))

from arg_marshall import (  # noqa: E402
    FOLKLORE_CREATEPROCESS_CHARS,
    measure_failure_curve,
    try_fork_execv,
    try_popen,
)

ART = REPO / "command-center" / "receipts" / "IMP-0424.json"
SENTINEL = "SENTINEL:IMP-0424:ARG-LIMIT-MEASURED"


def main() -> int:
    primary = measure_failure_curve(filler="A", try_spawn=try_popen)
    independent = measure_failure_curve(filler="B", try_spawn=try_fork_execv)
    summary = {
        "primary": {
            "instrument": primary.instrument,
            "filler": primary.filler,
            "first_fail_payload_len": primary.first_fail_payload_len,
            "threshold": primary.threshold,
            "fail_error_text": primary.fail_error_text,
        },
        "independent": {
            "instrument": independent.instrument,
            "filler": independent.filler,
            "first_fail_payload_len": independent.first_fail_payload_len,
            "threshold": independent.threshold,
            "fail_errno": independent.fail_errno,
            "fail_error_text": independent.fail_error_text,
        },
        "same_first_fail": independent.first_fail_payload_len
        == primary.first_fail_payload_len,
        "threshold_below_fail": independent.threshold
        < independent.first_fail_payload_len,
        "folklore_is_threshold": independent.threshold == FOLKLORE_CREATEPROCESS_CHARS,
    }
    print(json.dumps(summary, sort_keys=True))
    if independent.instrument == primary.instrument and independent.filler == primary.filler:
        print("FAILED:IMP-0424-probe2 same-fingerprint re-measure")
        return 1
    if independent.first_fail_payload_len != primary.first_fail_payload_len:
        print(
            "FAILED:IMP-0424-probe2 first_fail mismatch "
            f"{independent.first_fail_payload_len} != {primary.first_fail_payload_len}"
        )
        return 1
    if independent.threshold >= independent.first_fail_payload_len:
        print("FAILED:IMP-0424-probe2 threshold not below re-measured fail")
        return 1
    if independent.threshold == FOLKLORE_CREATEPROCESS_CHARS:
        print("FAILED:IMP-0424-probe2 remembered-constant threshold")
        return 1
    if not independent.fail_error_text:
        print("FAILED:IMP-0424-probe2 missing error text")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0424-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:IMP-0424-probe2 sentinel-absent")
        return 1
    print(
        f"primary_fail={primary.first_fail_payload_len} "
        f"independent_fail={independent.first_fail_payload_len} "
        f"independent_instrument={independent.instrument} "
        f"threshold={independent.threshold}"
    )
    print("SUCCESS:IMP-0424-probe2 independent-remeasure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
