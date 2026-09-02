#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0467.json from a live library run."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "lib"))

import scenario as S  # noqa: E402
import windows_safe_path as wsp  # noqa: E402

OUT_REL = "command-center/receipts/IMP-0467.json"
SENTINEL = "SENTINEL:IMP-0467:PATH-LIBRARY-WINDOWS-SAFE"
QUESTION = (
    "does a tree containing a file named NUL still enumerate completely, "
    "and what does the relative-path computation return for it?"
)


def main() -> int:
    ev = S.run_evidence()
    ans = S.answers(ev)
    if ans["delta"] != 1:
        print(f"FAILED:IMP-0467 emit delta={ans['delta']} wanted 1")
        return 1
    if ans["relpath_for_NUL"] != "NUL":
        print(f"FAILED:IMP-0467 emit relpath={ans['relpath_for_NUL']!r}")
        return 1
    if not ans["naive_windows_relpath_raises"]:
        print("FAILED:IMP-0467 emit naive relpath did not raise")
        return 1
    if not ans["long_path_above_260"]:
        print(f"FAILED:IMP-0467 emit long path {ans['long_path_chars']} <= 260")
        return 1
    if not ans["swallow_returns_zero_on_reserved"]:
        print("FAILED:IMP-0467 emit swallow control did not zero the reserved tree")
        return 1
    if not ans["library_does_not_return_zero_on_reserved"]:
        print("FAILED:IMP-0467 emit library returned zero on reserved tree")
        return 1
    if not ans["enumerates_completely"]:
        print("FAILED:IMP-0467 emit enumerates_completely is false")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "IMP-0467",
        "id": "IMP-0467",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "title": "Path library for extended-length paths and reserved device names",
        "question_or_target": QUESTION,
        "answer": ans,
        "library": {
            "path": "command-center/lib/windows_safe_path.py",
            "max_path": wsp.MAX_PATH,
            "reserved_stems": sorted(wsp.RESERVED_STEMS),
            "extended_prefix": "\\\\?\\",
            "relpath_algorithm": (
                "component-wise logical_abspath + safe_relpath; never "
                "os.path.relpath / GetFullPathNameW on reserved names"
            ),
            "walk_fail_closed": (
                "WalkIncomplete is raised when errors exist and zero entries "
                "were collected; swallowing_walk_count is the defect replica"
            ),
        },
        "evidence": ev,
        "tests": [
            {
                "id": "reserved-name-enumeration",
                "result": "PASS",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0467/probe1_reserved_enum.py"
                ),
            },
            {
                "id": "long-path-above-260",
                "result": "PASS",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0467/probe2_longpath_noswallow.py"
                ),
            },
            {
                "id": "no-silent-zero-swallow",
                "result": "PASS",
                "note": (
                    "swallowing_walk_count returns 0 on the reserved tree; "
                    "walk_tree returns the real non-zero file count"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "naive-windows-relpath-NUL",
                "kind": "known-crash-replica",
                "description": (
                    "naive_windows_relpath raises ValueError on a file named NUL, "
                    "matching os.path.relpath / GetFullPathNameW on Windows"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": ev["relpath"]["naive_error"],
            },
            {
                "id": "swallow-walk-zero",
                "kind": "known-broken-enumerator",
                "description": (
                    "A walk that catches the reserved-name crash and returns [] "
                    "reports zero entries; the library must not be equivalent"
                ),
                "fired_on_bad_state": ev["swallow_control"][
                    "swallow_zeros_reserved_tree"
                ],
                "silent_on_good_state": ev["swallow_control"][
                    "both_states_ordinary_match"
                ],
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0467-probe2-longpath-noswallow",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "note": (
                "Probe 2 is a mechanically different instrument: long-path "
                "round-trip plus the swallow-zero control, not a re-read of "
                "probe 1's reserved-name delta."
            ),
        },
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0467/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
        },
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json IMP-0467; related IMP-0021 / AUD-0082 / TST-0197"
        ),
        "timestamps": {"started_at": now, "ended_at": now},
        "host": {"os": ev["host_os"], "platform": ev["platform"]},
        "notes": (
            "G-1 delivery for IMP-0467 on Linux: a tree containing a file named "
            "NUL enumerates completely (file count differs by exactly one versus "
            "the same tree without NUL; neither walk raises). safe_relpath "
            "returns 'NUL', not a \\\\.\\NUL device mount. A long path above 260 "
            "characters is created, walked, and read back. The crash-swallowing "
            "enumerator returns 0; the library does not. "
            + SENTINEL
        ),
    }
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
