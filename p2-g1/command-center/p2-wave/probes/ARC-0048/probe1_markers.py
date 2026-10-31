#!/usr/bin/env python3
"""Probe 1: marker-payload per authorship surface, both-states, mention control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/phase3/A7/SECURITY.json"
SURFACES = ("skill", "workflow", "council", "marketplace")


def main() -> int:
    run = S.run_scenario()
    markers = run["markers"]
    print(f"scenario_pass={run['pass']} discipline={run['discipline_why']}")
    print(
        f"intact_any_reached={markers['intact_any_reached']} "
        f"mutant_any_reached={markers['mutant_any_reached']} "
        f"mention_silent={markers['mention_silent']} "
        f"intact_all_proposed={markers['intact_all_proposed']}"
    )
    for name in SURFACES:
        row = markers["intact"][name]
        print(f"intact[{name}] proposed={row['proposed']} reached={row['reached']} principal={row['principal']}")
        if not row["proposed"]:
            print(f"FAILED:ARC-0048-probe1 {name} inject did not propose (gullible decoder dead)")
            return 1
        if row["reached"]:
            print(f"FAILED:ARC-0048-probe1 {name} marker reached a tool call on intact design")
            return 1
        bad = markers["mutant_skip_taint"][name]
        print(f"mutant[{name}] proposed={bad['proposed']} reached={bad['reached']} principal={bad['principal']}")
    if not markers["mutant_any_reached"]:
        print("FAILED:ARC-0048-probe1 skip-taint mutant did not dispatch (both-states dead)")
        return 1
    if not markers["mention_silent"]:
        print("FAILED:ARC-0048-probe1 mention-only payload proposed a tool call")
        return 1
    if not run["pass"]:
        print("FAILED:ARC-0048-probe1 scenario did not pass")
        return 1
    if not ART.is_file():
        print("FAILED:ARC-0048-probe1 SECURITY.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0048-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:ARC-0048" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0048-probe1 sentinel absent")
        return 1
    live = doc.get("marker_payload") or {}
    if live.get("intact_any_reached") is not False:
        print("FAILED:ARC-0048-probe1 artifact intact_any_reached drift")
        return 1
    if live.get("mutant_any_reached") is not True:
        print("FAILED:ARC-0048-probe1 artifact mutant_any_reached drift")
        return 1
    if live.get("mention_silent") is not True:
        print("FAILED:ARC-0048-probe1 artifact mention_silent drift")
        return 1
    print("SUCCESS:ARC-0048-probe1 marker-payload both-states mention-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
