#!/usr/bin/env python3
"""Probe 1: re-run ablation; table and control must match the artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import catalog as C  # noqa: E402
import measure as M  # noqa: E402

ART = REPO / "command-center/research/RES-0102.json"
SENTINEL = (
    "SUCCESS:RES-0102 in the receipt AND a per-component ablation delta table "
    "including at least one approximately-zero control"
)


def main() -> int:
    live = M.run_experiment()
    table = live["ablation_delta_table"]
    control = live["approximately_zero_control"]
    print("live_baseline", live["baseline"])
    for row in table:
        print(
            f"live {row['component']} acc={row['accuracy']} "
            f"delta={row['delta_from_baseline']} "
            f"zero={row['approximately_zero']} control={row['is_control']}"
        )
    if not control["is_control"] or not control["approximately_zero"]:
        print("FAILED:RES-0102-probe1 control is not approximately zero")
        return 1
    if control["component"] != C.CONTROL_COMPONENT:
        print("FAILED:RES-0102-probe1 control component drifted")
        return 1
    named = {r["component"] for r in table}
    for need in C.COMPONENTS:
        if need not in named:
            print(f"FAILED:RES-0102-probe1 missing component {need}")
            return 1
    if not ART.is_file():
        print("FAILED:RES-0102-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:RES-0102-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:RES-0102-probe1 self-declared {doc.get('state')}")
        return 1
    art_table = {r["component"]: r for r in doc.get("ablation_delta_table") or []}
    for row in table:
        other = art_table.get(row["component"])
        if other is None:
            print(f"FAILED:RES-0102-probe1 artifact missing {row['component']}")
            return 1
        if other.get("n_correct") != row["n_correct"]:
            print(
                f"FAILED:RES-0102-probe1 n_correct drift {row['component']} "
                f"live={row['n_correct']} art={other.get('n_correct')}"
            )
            return 1
        if other.get("approximately_zero") != row["approximately_zero"]:
            print(f"FAILED:RES-0102-probe1 zero-flag drift {row['component']}")
            return 1
    art_ctrl = doc.get("approximately_zero_control") or {}
    if art_ctrl.get("component") != C.CONTROL_COMPONENT:
        print("FAILED:RES-0102-probe1 artifact control component")
        return 1
    if art_ctrl.get("approximately_zero") is not True:
        print("FAILED:RES-0102-probe1 artifact control not zero")
        return 1
    print(
        "SUCCESS:RES-0102-probe1 ablation table recomputed; "
        f"control={C.CONTROL_COMPONENT} delta={control['delta_from_baseline']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
