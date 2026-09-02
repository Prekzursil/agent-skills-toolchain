#!/usr/bin/env python3
"""Probe 2: far-end delivered value vs intended (git %B, capture JSON, launcher file, SHA).

Mechanically different from probe 1: verdicts are computed only from delivered_equals_intended
and oracle SHA match, never from exit codes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

WORK = HERE / "_work" / "probe2"


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    matrix = E.run_matrix(WORK)
    summary = E.summarize(matrix)
    mismatches = []
    far_end_ok = 0
    far_end_n = 0
    for cell in matrix["cells"]:
        cid = cell["construction_id"]
        pid = cell["payload_id"]
        # Native/control ASCII and native argv must round-trip at the far end.
        watch = (
            pid == "P01-ASCII-CONTROL"
            and cid in ("C01-GIT-COMMIT-MESSAGE", "C07-NATIVE-ARGV-BOUNDARY")
        ) or cid == "C07-NATIVE-ARGV-BOUNDARY"
        if not watch:
            continue
        far_end_n += 1
        eq = bool(cell.get("delivered_equals_intended"))
        if eq:
            far_end_ok += 1
        else:
            mismatches.append(
                {
                    "id": cell["id"],
                    "outcome": cell["outcome"],
                    "exit_code": cell["exit_code"],
                    "intended_sha256": cell.get("intended_sha256"),
                    "delivered_sha256": (cell.get("delivered") or {}).get("sha256")
                    if isinstance(cell.get("delivered"), dict)
                    else None,
                }
            )
    clip = matrix["windows_clip_control"]
    out = {
        "probe": "probe2-delivered-value",
        "unit_id": E.UNIT,
        "n_cells": matrix["n_cells"],
        "far_end_control_checked": far_end_n,
        "far_end_control_ok": far_end_ok,
        "far_end_mismatches": mismatches,
        "windows_clip_fired": bool(clip.get("fired_on_bad_state")),
        "windows_clip_outcome": clip.get("outcome"),
        "overall_verdict": summary["overall_verdict"],
        "targets": summary["targets"],
        "tests": summary["tests"],
        "pass": far_end_n > 0 and far_end_ok == far_end_n and bool(clip.get("fired_on_bad_state")),
    }
    (WORK / "probe2.json").write_text(
        json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, indent=2, sort_keys=True))
    if not out["pass"]:
        print("FAILED:ADV-0118-probe2 far-end delivered-value check")
        return 1
    print("SUCCESS:ADV-0118-probe2 delivered-value round-trip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
