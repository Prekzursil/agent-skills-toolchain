#!/usr/bin/env python3
"""Probe 1: both-states preservation control.

A workflow file that exists only in one worktree must be UNIQUE-NOWHERE-ELSE.
After a byte-identical copy is placed on origin/main, the same digest must
flip to PRESERVED with that origin location recorded. Ancestry is not used.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from estate import both_states_unique_then_preserve  # noqa: E402
from sweep import PRESERVED, UNIQUE  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0015-sweep-worktrees.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0015-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0015" not in text:
        print("FAILED:WFA-0015-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0015-probe1 self-declared", st)
        return 1

    with tempfile.TemporaryDirectory(prefix="wfa0015-p1-") as tmp:
        result = both_states_unique_then_preserve(Path(tmp))
    if not result.get("pass"):
        print("FAILED:WFA-0015-probe1 both-states did not flip")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1
    if result["before_class"] != UNIQUE or result["after_class"] != PRESERVED:
        print("FAILED:WFA-0015-probe1 class mismatch", result)
        return 1
    if not result["after_locs"]:
        print("FAILED:WFA-0015-probe1 PRESERVED without location")
        return 1

    ctrl = doc.get("both_states_control") or {}
    if ctrl.get("unique_state") != UNIQUE or ctrl.get("preserved_state") != PRESERVED:
        print("FAILED:WFA-0015-probe1 artifact both_states_control mismatch")
        return 1

    payload = {
        "pass": True,
        "probe": "probe1-both-states",
        "unit_id": "WFA-0015",
        "before_class": result["before_class"],
        "after_class": result["after_class"],
        "after_locs": result["after_locs"],
        "digest": result["digest"],
        "signals": [
            "content-hash-not-ancestry",
            "PRESERVED-requires-recorded-location",
        ],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "unique_then_preserved "
        f"before={result['before_class']} after={result['after_class']} "
        f"loc={result['after_locs'][0]}"
    )
    print("SUCCESS:WFA-0015-probe1 unique file flips to PRESERVED with origin location")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
