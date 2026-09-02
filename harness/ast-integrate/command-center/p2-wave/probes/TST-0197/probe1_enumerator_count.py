#!/usr/bin/env python3
"""Probe 1: enumerator count, known-present detector control, NUL relpath seed.

Signal (a): the enumerator's returned count with reserved names present.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import campaign as C  # noqa: E402
import enumerator as E  # noqa: E402

ART = REPO / "command-center/receipts/TST-0197.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0197-probe1 {msg}")
    return 1


def main() -> int:
    result = C.run_campaign()
    checks = result["checks"]
    enum_h = result["enumerator_hostile"]
    planted = result["planted_hostile"]
    seed = result["regression_seed"]

    if not checks["known_present_found"]:
        return fail("detector control: known-present ordinary file not found")
    if not checks["enumerator_no_exception"]:
        return fail(
            f"enumerator exception or incomplete "
            f"exc={enum_h.get('exception')} errors={enum_h.get('errors')}"
        )
    if not checks["enumerator_not_silent_zero"]:
        return fail(f"silent zero count={enum_h.get('count')}")
    if not checks["reserved_reported"]:
        return fail(
            f"reserved not fully reported found={enum_h.get('reserved_basenames_found')}"
        )
    if enum_h["count"] != planted["planted_count"]:
        return fail(
            f"enumerator count {enum_h['count']} != planted {planted['planted_count']}"
        )
    if not checks["ntpath_nul_valueerror"]:
        return fail(f"regression seed did not raise ValueError: {seed}")
    if "path is on mount" not in (seed.get("nul_message") or ""):
        return fail(f"ValueError message missing mount clause: {seed.get('nul_message')}")
    if not checks["posix_relpath_does_not_raise"]:
        return fail("posix relpath raised on planted NUL (unexpected on Linux)")
    if not checks["naive_walk_raises"]:
        return fail("naive ntpath walk did not raise")
    if not checks["naive_swallow_is_silent_zero"]:
        return fail("swallowed naive walk was not a silent zero")
    if not checks["ordinary_tree_no_reserved"]:
        return fail("ordinary-only tree reported reserved names or missed known-present")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"receipt self-declared {doc.get('state')}")
        blob = json.dumps(doc)
        if "SUCCESS:TST-0197" not in blob:
            return fail("receipt sentinel absent")
        pub = (doc.get("evidence") or {}).get("enumerator_count") or {}
        if pub.get("count") != enum_h["count"]:
            return fail(
                f"receipt enumerator count {pub.get('count')} != live {enum_h['count']}"
            )

    summary = {
        "probe": "probe1-enumerator-count",
        "unit_id": "TST-0197",
        "pass": True,
        "count": enum_h["count"],
        "reserved": enum_h["reserved_basenames_found"],
        "known_present_found": True,
        "complete": True,
        "ntpath_nul_valueerror": True,
        "used_os_path_relpath": enum_h["used_os_path_relpath"],
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"count={enum_h['count']} reserved={enum_h['reserved_basenames_found']} "
        f"known_present=True seed={seed['nul_message']}"
    )
    print(
        "SUCCESS:TST-0197-probe1 enumerator complete count with reserved "
        "entries; ntpath.relpath ValueError on \\\\.\\NUL"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
