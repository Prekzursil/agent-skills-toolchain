#!/usr/bin/env python3
"""Probe 1: planted deletion and planted truncation both BLOCK the report write.

Both-states: a fresh sandbox with an intact manifest PERMITS the write (exit 0).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    MIN_BYTES,
    sandbox,
    run_clean,
    run_deletion,
    run_truncation,
)


def fail(reason: str) -> int:
    print(f"FAILED:SYN-0019-probe1 {reason}")
    return 1


def main() -> int:
    with sandbox("syn0019-p1-clean-") as clean_root:
        clean = run_clean(clean_root)
    with sandbox("syn0019-p1-del-") as del_root:
        deleted = run_deletion(del_root)
    with sandbox("syn0019-p1-trunc-") as trunc_root:
        truncated = run_truncation(trunc_root)

    trunc_min = "minimum-size" in (truncated.get("entry_conditions") or [])
    ok = (
        clean["verdict"] == "PERMITTED"
        and clean["exit_code"] == 0
        and clean["wrote"] is True
        and clean["output_exists"] is True
        and deleted["verdict"] == "BLOCKED"
        and deleted["exit_code"] != 0
        and deleted["wrote"] is False
        and deleted["output_exists"] is False
        and "missing-artifact" in (deleted.get("verification_blocking_conditions") or [])
        and truncated["verdict"] == "BLOCKED"
        and truncated["exit_code"] != 0
        and truncated["wrote"] is False
        and truncated["output_exists"] is False
        and trunc_min
        and truncated.get("truncated_bytes") == 0
    )
    payload = {
        "probe": "probe1-planted-deletion-and-truncation",
        "unit_id": "SYN-0019",
        "pass": ok,
        "min_bytes": MIN_BYTES,
        "clean": {
            "verdict": clean["verdict"],
            "exit_code": clean["exit_code"],
            "wrote": clean["wrote"],
            "timestamp": clean["timestamp"],
        },
        "planted_deletion": {
            "verdict": deleted["verdict"],
            "exit_code": deleted["exit_code"],
            "wrote": deleted["wrote"],
            "timestamp": deleted["timestamp"],
            "blocking_conditions": deleted.get("verification_blocking_conditions"),
        },
        "planted_truncation": {
            "verdict": truncated["verdict"],
            "exit_code": truncated["exit_code"],
            "wrote": truncated["wrote"],
            "timestamp": truncated["timestamp"],
            "entry_conditions": truncated.get("entry_conditions"),
            "truncated_bytes": truncated.get("truncated_bytes"),
        },
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not ok:
        return fail(
            "clean-must-PERMITTED-exit0; deletion-and-truncation-must-BLOCK-and-not-write"
        )
    print(
        "SUCCESS:SYN-0019-probe1 deletion BLOCKED, truncation BLOCKED on "
        "minimum-size, clean PERMITTED exit 0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
