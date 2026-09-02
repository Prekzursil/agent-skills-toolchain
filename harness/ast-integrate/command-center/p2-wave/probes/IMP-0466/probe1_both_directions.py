#!/usr/bin/env python3
"""Probe 1: both directions under one scoped configuration.

A revision argument survives unconverted AND a legitimate POSIX path still
converts (clone marker exists on the intended Windows path). Conversion-on
(mode=none) must still corrupt the revision, or this probe is silent in both
states.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.shell.pathconv import (  # noqa: E402
    both_directions_report,
    posix_to_win,
)

UID = "IMP-0466"


def main() -> int:
    report = both_directions_report()
    scoped = report["scoped"]
    none = report["conversion_on"]
    payload = {
        "probe": "probe1-both-directions",
        "unit_id": UID,
        "pass": report["pass"],
        "same_configuration": report["same_configuration"],
        "revision_original": scoped["revision_original"],
        "revision_observed_scoped": scoped["revision_observed"],
        "revision_unconverted": scoped["revision_unconverted"],
        "device_original": scoped["device_original"],
        "device_observed_scoped": scoped["device_observed"],
        "device_unconverted": scoped["device_unconverted"],
        "posix_original": scoped["posix_original"],
        "posix_observed_scoped": scoped["posix_observed"],
        "posix_converted": scoped["posix_converted"],
        "clone_intended_exists": scoped["clone_intended_exists"],
        "clone_marker": scoped["clone_marker"],
        "conversion_on_revision_observed": none["revision_observed"],
        "conversion_on_revision_corrupted": none["revision_corrupted"],
        "conversion_on_device_observed": none["device_observed"],
        "expected_win_posix": posix_to_win(scoped["posix_original"]),
        "expected_win_rev_if_converted": posix_to_win(scoped["revision_original"]),
        "scoped_env_has_MSYS_NO_PATHCONV": "MSYS_NO_PATHCONV" in scoped["env_clone"],
    }
    print(json.dumps(payload, sort_keys=True))

    if not report["same_configuration"]:
        print("FAILED:IMP-0466-probe1 scoped env used global suppression")
        return 1
    if payload["scoped_env_has_MSYS_NO_PATHCONV"]:
        print("FAILED:IMP-0466-probe1 production path set MSYS_NO_PATHCONV")
        return 1
    if not scoped["revision_unconverted"]:
        print("FAILED:IMP-0466-probe1 revision was converted under scoped mode")
        return 1
    if not scoped["device_unconverted"]:
        print("FAILED:IMP-0466-probe1 /dev/null was converted under scoped mode")
        return 1
    if not scoped["posix_converted"]:
        print("FAILED:IMP-0466-probe1 POSIX path was not converted under scoped mode")
        return 1
    if not scoped["clone_intended_exists"]:
        print("FAILED:IMP-0466-probe1 clone intended path missing (exit-code is not evidence)")
        return 1
    if not none["revision_corrupted"]:
        print("FAILED:IMP-0466-probe1 conversion-on did not mangle revision (dead probe)")
        return 1
    if not none["device_corrupted"]:
        print("FAILED:IMP-0466-probe1 conversion-on did not mangle /dev/null (dead probe)")
        return 1
    if not none["posix_converted"]:
        print("FAILED:IMP-0466-probe1 conversion-on failed to convert POSIX path")
        return 1
    if not report["pass"]:
        print("FAILED:IMP-0466-probe1 both-directions contract")
        return 1
    print(
        "SUCCESS:IMP-0466-probe1 revision+device intact and POSIX path converted "
        "under the same scoped configuration"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
