#!/usr/bin/env python3
"""Named probe 2: planted-file detector + reserved-name walker.

Different field than probe 1 (sha set equality). This probe re-runs the
DETECTOR CONTROL on a known-broken incomplete rollback and confirms the
walker enumerates NUL via the extended-length prefix instead of swallowing
to zero files.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from rehearse import report_payload, run_planted_control, run_walker_control  # noqa: E402
from scenario import PLANTED_REL, RESERVED_REL  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0041-rollback-byte-parity.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0041-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    payload = report_payload(doc)

    with tempfile.TemporaryDirectory(prefix="cnf0041-p2-") as tmp:
        root = Path(tmp)
        planted = run_planted_control(root / "plant")
        walker = run_walker_control(root / "walk")

    if not planted.get("detected"):
        print("FAILED:CNF-0041-probe2 detector-failure")
        print(json.dumps(planted, indent=2, default=str)[:3000])
        return 1
    if planted.get("planted_path") != PLANTED_REL:
        print("FAILED:CNF-0041-probe2 unexpected plant", planted.get("planted_path"))
        return 1
    if PLANTED_REL not in (planted.get("symmetric_difference") or {}).get("only_in_post", []):
        print("FAILED:CNF-0041-probe2 plant not in only_in_post")
        return 1

    recorded = payload.get("planted_file_control") or {}
    if recorded.get("detected") is not True:
        print("FAILED:CNF-0041-probe2 artifact planted control not detected")
        return 1
    if recorded.get("planted_path") != PLANTED_REL:
        print("FAILED:CNF-0041-probe2 artifact plant path drift")
        return 1

    if not walker.get("naive_swallowed_to_zero"):
        print("FAILED:CNF-0041-probe2 naive walker did not report zero")
        print(json.dumps(walker, indent=2, default=str)[:2000])
        return 1
    if walker.get("safe_count", 0) < 2 or not walker.get("reserved_in_safe"):
        print("FAILED:CNF-0041-probe2 walker-crash")
        print(json.dumps(walker, indent=2, default=str)[:2000])
        return 1
    if walker.get("reserved_path") != RESERVED_REL:
        print("FAILED:CNF-0041-probe2 reserved path", walker.get("reserved_path"))
        return 1

    rec_w = payload.get("reserved_name_walker") or {}
    if rec_w.get("extended_length_prefix_applied") is not True:
        print("FAILED:CNF-0041-probe2 artifact missing extended-length")
        return 1
    if rec_w.get("naive_swallowed_to_zero") is not True:
        print("FAILED:CNF-0041-probe2 artifact naive control missing")
        return 1
    if rec_w.get("safe_count") != walker["safe_count"]:
        print(
            "FAILED:CNF-0041-probe2 safe_count drift "
            f"live={walker['safe_count']} recorded={rec_w.get('safe_count')}"
        )
        return 1

    out = {
        "probe": "probe2-planted-control",
        "unit_id": "CNF-0041",
        "planted_path": PLANTED_REL,
        "detected": True,
        "reserved_path": RESERVED_REL,
        "extended_length_prefix_applied": True,
        "naive_swallowed_to_zero": True,
        "safe_count": walker["safe_count"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"planted={PLANTED_REL} detected=True reserved={RESERVED_REL} "
        f"naive_zero={walker['naive_count']} safe={walker['safe_count']}"
    )
    print("SUCCESS:CNF-0041-probe2 planted-file detector and reserved-name walker")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
