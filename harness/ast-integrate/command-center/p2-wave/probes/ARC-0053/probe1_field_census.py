#!/usr/bin/env python3
"""Probe 1: recursive schema field census vs COST.json headline."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

REPO = C.REPO
COST = REPO / "command-center/phase3/A8/COST.json"


def main() -> int:
    m = C.measure()
    if not m["agree"]:
        print("FAILED:ARC-0053-probe1 recursive vs iterative vs required disagree")
        print(f" rec={m['recursive_paths']}")
        print(f" it={m['iterative_paths']}")
        print(f" req={m['required_paths']}")
        return 1
    if not m["skip_ref_differs"]:
        print("FAILED:ARC-0053-probe1 skip-$ref control did not differ")
        return 1
    if m["workflow_string_slots"] < 1 or m["preset_string_slots"] < 1:
        print("FAILED:ARC-0053-probe1 empty slot census")
        return 1
    if m["live_registry_workflow_entries"] < 1:
        print("FAILED:ARC-0053-probe1 no live workflow_blueprint in registry")
        return 1
    if m["live_registry_preset_entries"] < 1:
        print("FAILED:ARC-0053-probe1 no live council_preset in registry")
        return 1
    if not COST.is_file():
        print("FAILED:ARC-0053-probe1 COST.json missing")
        return 1
    doc = json.loads(COST.read_text(encoding="utf-8"))
    want = m["user_facing_strings"]
    got = doc["headline"]["user_facing_strings"]
    print(
        f"slots_wf={m['workflow_string_slots']} "
        f"slots_preset={m['preset_string_slots']} "
        f"strings={want} help_topics={m['help_topics']} examples={m['examples']}"
    )
    print(f"paths={m['recursive_paths']}")
    print(f"skip_ref_paths={m['skip_ref_paths']}")
    print(
        f"live_wf={m['live_registry_workflow_entries']} "
        f"live_preset={m['live_registry_preset_entries']}"
    )
    if got != want:
        print(f"FAILED:ARC-0053-probe1 COST headline {got} != live {want}")
        return 1
    if doc["headline"]["help_topics"] != m["help_topics"]:
        print("FAILED:ARC-0053-probe1 help_topics mismatch")
        return 1
    if doc["headline"]["examples"] != m["examples"]:
        print("FAILED:ARC-0053-probe1 examples mismatch")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0053-probe1 COST state={doc.get('state')}")
        return 1
    print("SUCCESS:ARC-0053-probe1 recursive field census matches COST.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
