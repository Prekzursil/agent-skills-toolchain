#!/usr/bin/env python3
"""Probe 1: both-states control — drop one gate, detector names it; drop nothing, empty diff."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center"))

from foundry.capability_diff import both_states  # noqa: E402

ART = REPO / "command-center/foundry/WFA-0140-capability-loss-detector-for-fusion.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0140-probe1 {msg}")
    return 1


def main() -> int:
    live = both_states()
    if not live["intact_empty"]:
        return fail(f"intact fusion not empty: {live['intact_absent']}")
    if not live["named_on_removal"]:
        return fail(f"stripped fusion did not name {live['removed_gate']}: {live['named_missing']}")
    if live["stripped_classifications"].get("gates:human-ack") != "UNNOTICED":
        return fail("planted gate drop must be UNNOTICED (no recording line)")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:WFA-0140" not in text:
        return fail("sentinel absent")
    recorded = doc.get("both_states") or {}
    if recorded.get("removed_gate") != live["removed_gate"]:
        return fail("artifact removed_gate drift")
    if recorded.get("intact_empty") is not True:
        return fail("artifact intact_empty is not true")
    if recorded.get("named_on_removal") is not True:
        return fail("artifact named_on_removal is not true")
    if recorded.get("pass") is not True:
        return fail("artifact both_states.pass is not true")
    tests = {t["id"]: t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    if (tests.get("both-states-gate-drop") or {}).get("result") != "PASS":
        return fail("artifact test both-states-gate-drop not PASS")
    print(
        json.dumps(
            {
                "probe": "probe1-both-states",
                "unit_id": "WFA-0140",
                "removed_gate": live["removed_gate"],
                "intact_empty": live["intact_empty"],
                "named_on_removal": live["named_on_removal"],
                "named_missing": live["named_missing"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"intact_empty={live['intact_empty']} named_on_removal={live['named_on_removal']} "
        f"gate={live['removed_gate']}"
    )
    print("SUCCESS:WFA-0140-probe1 both-states gate drop named, intact empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
