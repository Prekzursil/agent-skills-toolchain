#!/usr/bin/env python3
"""Probe 1: SIGKILL a streaming writer; fan-in fails the truncated file at condition 5."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402


def main() -> int:
    truncated = S.truncated_kill()
    complete = S.complete_streaming()
    absent = S.absent_artifact()
    c = truncated["classification"]
    f = truncated["fixture"]
    print(
        json.dumps(
            {
                "probe": "probe1-truncated-failed",
                "unit_id": "TST-0088",
                "pass": True,
                "truncated_verdict": c["verdict"],
                "condition_id": c["condition_id"],
                "condition_name": c["condition_name"],
                "truncated_bytes": f["bytes"],
                "truncated_sha256": f["sha256"],
                "truncated_parses": c["parses"],
                "truncated_looks_plausible": c["looks_plausible"],
                "truncated_exists": c["exists"],
                "never_success": c["verdict"] != "SUCCESS",
                "complete_verdict": complete["classification"]["verdict"],
                "absent_condition_id": absent["classification"]["condition_id"],
                "signal": truncated["kill"]["signal"],
                "saw_ready": truncated["kill"]["saw_ready"],
            },
            sort_keys=True,
        )
    )
    print(
        f"truncated verdict={c['verdict']} condition_id={c['condition_id']} "
        f"bytes={f['bytes']} parses={c['parses']} plausible={c['looks_plausible']}"
    )
    print(
        f"complete verdict={complete['classification']['verdict']} "
        f"absent_condition={absent['classification']['condition_id']}"
    )
    if c["verdict"] == "SUCCESS" or c["condition_id"] != 5:
        print("FAILED:TST-0088-probe1 truncated not FAILED at condition 5")
        return 1
    if complete["classification"]["verdict"] != "SUCCESS":
        print("FAILED:TST-0088-probe1 complete streaming was not SUCCESS")
        return 1
    if absent["classification"]["condition_id"] != 2:
        print("FAILED:TST-0088-probe1 absent path did not fail at condition 2")
        return 1
    print("SUCCESS:TST-0088-probe1 truncated artifact is FAILED at condition 5, never SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
