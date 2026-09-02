#!/usr/bin/env python3
"""Probe 1: both-states TOCTOU. Activation-time catches; index-time slips."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import sequence as S  # noqa: E402

ART = REPO / "command-center/phase3/A4/SECURITY.json"
DESIGN = REPO / "command-center/phase3/A4/DESIGN.json"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0027-probe1 {msg}")
    return 1


def main() -> int:
    live = S.both_states()
    print(f"index_slipped={live['index_slipped']}")
    print(f"activation_caught={live['activation_caught']}")
    print(f"selection_also_slips={live['selection_also_slips']}")
    if not live["pass"]:
        return fail("live both-states failed")
    if DESIGN.is_file():
        return fail("A4 DESIGN.json present; rebuild circle")
    if not ART.is_file():
        return fail("SECURITY.json missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:ARC-0027" not in text:
        return fail("sentinel absent")
    both = doc.get("both_states") or {}
    if both.get("index_slipped") is not True:
        return fail("artifact index_slipped")
    if both.get("activation_caught") is not True:
        return fail("artifact activation_caught")
    if both.get("selection_also_slips") is not True:
        return fail("artifact selection_also_slips")
    if both.get("index_activate_outcome") != live["index"]["activate_outcome"]:
        return fail("index outcome drift")
    if both.get("activation_activate_outcome") != live["activation"]["activate_outcome"]:
        return fail("activation outcome drift")
    printed = both.get("printed_index") or []
    if not any("GRANT" in str(x) and "index" in str(x) for x in printed):
        return fail("grants not printed at index")
    if not any("GRANT" in str(x) and "activate" in str(x) for x in printed):
        return fail("grants not printed at activate")
    if "tool:Bash" not in str(both.get("index_effective_grant")):
        return fail("index slip missing tool:Bash grant")
    if "tool:Bash" in str(both.get("activation_effective_grant")):
        return fail("activation epoch applied escalated grant")
    print("SUCCESS:ARC-0027-probe1 both-states TOCTOU")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
