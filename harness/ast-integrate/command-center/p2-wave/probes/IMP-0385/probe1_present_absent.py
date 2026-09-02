#!/usr/bin/env python3
"""Probe 1: known-present capability AND known-absent sentinel (detector control).

A crawler that always returns 1 fails the absent id. A crawler that always
returns 0 fails the present id. Per-root file counts must match an independent
shell census (pwsh Get-ChildItem, else find) to within ZERO.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from fixtures import (  # noqa: E402
    CENSUS_PS1,
    EXPECTED_KINDS,
    KNOWN_ABSENT,
    KNOWN_PRESENT,
    fixture_roots,
)
from tools.router.index_build import build_index  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0385-probe1 {msg}")
    return 1


def main() -> int:
    roots = fixture_roots()
    for root_id, path in roots.items():
        if not path.is_dir():
            return fail(f"fixture root missing {root_id}={path}")

    index = build_index(roots, ps1=CENSUS_PS1)
    caps = index.get("capabilities") or {}
    present_n = 1 if KNOWN_PRESENT in caps else 0
    absent_n = 1 if KNOWN_ABSENT in caps else 0

    if present_n != 1:
        return fail(f"known-present {KNOWN_PRESENT} count={present_n} want=1")
    if absent_n != 0:
        return fail(f"known-absent {KNOWN_ABSENT} count={absent_n} want=0")
    if index.get("aborted_roots"):
        return fail(f"aborted_roots={index['aborted_roots']}")

    kinds = {str(c.get("kind")) for c in caps.values()}
    missing_kinds = [k for k in EXPECTED_KINDS if k not in kinds]
    if missing_kinds:
        return fail(f"kinds missing {missing_kinds} have={sorted(kinds)}")

    if caps[KNOWN_PRESENT].get("kind") != "skill":
        return fail("known-present is not classified as skill")

    # notes.txt / README.md must be walked (file_count>0) but not become capabilities.
    decoys = [
        cid
        for cid, rec in caps.items()
        if str(rec.get("relpath") or "").lower() in {"notes.txt", "readme.md"}
        or str(rec.get("source_basename") or "").lower() in {"notes.txt", "readme.md"}
    ]
    if decoys:
        return fail(f"decoy files classified as capabilities {decoys}")

    parity_rows = []
    for row in index.get("per_root") or []:
        diff = row.get("diff")
        if diff != 0:
            return fail(
                f"parity {row.get('root_id')} crawler={row.get('crawler_file_count')} "
                f"census={row.get('census_file_count')} diff={diff} "
                f"engine={((row.get('census') or {}).get('chosen_engine'))}"
            )
        if row.get("crawler_file_count") == 0 and row.get("status") == "walked":
            # Every fixture root has at least one file (detector against crash-as-zero).
            return fail(f"walked root {row.get('root_id')} reported file_count=0")
        parity_rows.append(
            {
                "root_id": row.get("root_id"),
                "crawler_file_count": row.get("crawler_file_count"),
                "census_file_count": row.get("census_file_count"),
                "diff": diff,
                "engine": (row.get("census") or {}).get("chosen_engine"),
                "capability_count": row.get("capability_count"),
            }
        )

    if not index.get("zero_diff"):
        return fail("zero_diff is false after per-root diffs of 0")

    payload = {
        "probe": "probe1-present-absent-parity",
        "unit_id": "IMP-0385",
        "pass": True,
        "known_present": KNOWN_PRESENT,
        "known_absent": KNOWN_ABSENT,
        "present_count": present_n,
        "absent_count": absent_n,
        "capability_count": index.get("capability_count"),
        "capability_ids": sorted(caps),
        "kinds": sorted(kinds),
        "parity": parity_rows,
        "zero_diff": True,
        "detector_control": {
            "present_is_one": present_n == 1,
            "absent_is_zero": absent_n == 0,
            "not_always_one": absent_n == 0,
            "not_always_zero": present_n == 1,
        },
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    print(
        f"present={present_n} absent={absent_n} caps={index.get('capability_count')} "
        f"zero_diff={index.get('zero_diff')}"
    )
    print("SUCCESS:IMP-0385-probe1 present-absent detector control and census parity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
