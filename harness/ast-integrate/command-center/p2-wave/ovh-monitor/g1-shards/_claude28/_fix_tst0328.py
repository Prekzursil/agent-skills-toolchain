#!/usr/bin/env python3
"""shard-01 scratch: refresh TST-0328 receipt census snapshot from live census."""
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
sys.path.insert(0, str(REPO))
from tools.test_support.census import census  # noqa: E402

live = census(REPO)
adoption = live.get("adoption") or {}
registry = live.get("registry") or {}
live_scan = live.get("live") or {}
live_users = list(live_scan.get("fixture_users") or [])
live_hands = list(live_scan.get("hand_rolled") or [])
print("live users:", len(live_users), "hands:", len(live_hands), "registry present:", registry.get("present"))

p1 = "command-center/p2-wave/probes/TST-0328/probe1_selftest.py"
p2 = "command-center/p2-wave/probes/TST-0328/probe2_census_and_reviewer.py"
print("probes in users:", p1 in live_users, p2 in live_users)

art = REPO / "command-center/receipts/TST-0328.json"
doc = json.loads(art.read_text(encoding="utf-8"))
ev = doc.get("evidence") or {}
cen = ev.get("census") or {}
old_users = list((cen.get("live") or {}).get("fixture_users") or [])
print("old rec users:", len(old_users))

cen["live"] = {"fixture_users": live_users, "hand_rolled": live_hands}
rec_adopt = cen.get("adoption") or {}
rec_adopt["live_fixture_users"] = len(live_users)
rec_adopt["live_hand_rolled"] = len(live_hands)
rec_adopt["registry_present"] = bool(registry.get("present"))
if "registered_detectors" in rec_adopt and adoption.get("registered_detectors") is not None:
    rec_adopt["registered_detectors"] = adoption.get("registered_detectors")
cen["adoption"] = rec_adopt
ev["census"] = cen
doc["evidence"] = ev

if "--write" in sys.argv:
    art.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    print("WROTE receipt")
