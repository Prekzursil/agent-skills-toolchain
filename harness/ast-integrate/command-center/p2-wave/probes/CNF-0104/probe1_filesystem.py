#!/usr/bin/env python3
"""Named probe 1: both filesystem classes + non-colliding control on each.

Re-runs the installer matrix against a real POSIX tempdir and a real VFAT
loop mount. Does not trust the artifact's conclusion until the live rerun
matches the recorded flags.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from constants import COMPLETION_SENTINEL, OUT_REL, UNIT_ID  # noqa: E402
from scenario import run_filesystem_matrix  # noqa: E402

ART = REPO / OUT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0104-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT_ID:
        print("FAILED:CNF-0104-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0104-probe1 self-declared {doc.get('state')}")
        return 1
    if COMPLETION_SENTINEL not in text:
        print("FAILED:CNF-0104-probe1 completion_sentinel absent")
        return 1

    live = run_filesystem_matrix()
    printable = {
        "both_exercised": live.get("both_exercised"),
        "control_survived_on_each": live.get("control_survived_on_each"),
        "platform_divergence": live.get("platform_divergence"),
        "posix_outcome": (live.get("case_sensitive") or {}).get("collision_outcome"),
        "vfat_outcome": (live.get("case_insensitive") or {}).get("collision_outcome"),
        "vfat_last_wins": (live.get("case_insensitive") or {}).get("last_wins_proven"),
    }
    print(json.dumps(printable, sort_keys=True))

    if live.get("both_exercised") is not True:
        print("FAILED:CNF-0104-probe1 both filesystem classes were not exercised")
        return 1
    if live.get("control_survived_on_each") is not True:
        print("FAILED:CNF-0104-probe1 non-colliding control did not survive on each class")
        return 1
    if live.get("platform_divergence") is not True:
        print("FAILED:CNF-0104-probe1 no POSIX-vs-VFAT divergence")
        return 1
    if (live.get("case_sensitive") or {}).get("collision_outcome") != "both-names-coexist":
        print("FAILED:CNF-0104-probe1 POSIX did not keep both names")
        return 1
    if (live.get("case_insensitive") or {}).get("collision_outcome") != "silent-last-wins":
        print("FAILED:CNF-0104-probe1 VFAT was not silent last-wins")
        return 1
    if not (live.get("case_insensitive") or {}).get("last_wins_proven"):
        print("FAILED:CNF-0104-probe1 last-wins not proven by reversed write order")
        return 1

    payload = doc.get("report") if isinstance(doc.get("report"), dict) else doc
    rec_fs = payload.get("filesystem_classes") or {}
    rec_ctrl = (payload.get("controls") or {}).get("non_colliding_filenames") or {}
    if rec_fs.get("both_exercised") is not True:
        print("FAILED:CNF-0104-probe1 artifact both_exercised false")
        return 1
    if rec_ctrl.get("survived_on_each") is not True:
        print("FAILED:CNF-0104-probe1 artifact control survived_on_each false")
        return 1
    if rec_fs.get("platform_divergence") is not True:
        print("FAILED:CNF-0104-probe1 artifact platform_divergence false")
        return 1
    rec_posix = (rec_fs.get("case_sensitive") or {}).get("collision_outcome")
    rec_vfat = (rec_fs.get("case_insensitive") or {}).get("collision_outcome")
    if rec_posix != live["case_sensitive"]["collision_outcome"]:
        print("FAILED:CNF-0104-probe1 artifact POSIX outcome drift")
        return 1
    if rec_vfat != live["case_insensitive"]["collision_outcome"]:
        print("FAILED:CNF-0104-probe1 artifact VFAT outcome drift")
        return 1

    print("SUCCESS:CNF-0104-probe1 both filesystem classes and control survival")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
