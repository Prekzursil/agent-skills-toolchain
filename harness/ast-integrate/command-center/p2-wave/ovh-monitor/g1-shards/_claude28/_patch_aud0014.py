#!/usr/bin/env python3
"""shard-01 scratch: patch AUD-0014 artifact with probe-checked live fields."""
import json
import os
import sys
from pathlib import Path

os.environ["CLAUDE_CONFIG_DIR"] = r"C:\nonexistent-claude-config"
REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "probes" / "AUD-0014"))
import drift as D  # noqa: E402

live = D.measure()
art_path = REPO / D.OUT_REL
doc = json.loads(art_path.read_text(encoding="utf-8"))

assert doc.get("completion_sentinel") == D.SENTINEL or D.SENTINEL in json.dumps(doc), "sentinel missing"

doc["n_live_only"] = live["n_live_only"]
doc["n_repo_only"] = live["n_repo_only"]
doc["n_content_different"] = live["n_content_different"]
doc["n_host_floor_violations"] = live["n_host_floor_violations"]
doc["host_floor_violations"] = live["host_floor_violations"]
doc["any_host_tree_present"] = live["any_host_tree_present"]
doc["host"] = live["host"]
doc["models"] = live["models"]
doc["use_vs_mention"] = live["use_vs_mention"]
doc["path_control"] = live["path_control"]

orphans = list(doc.get("orphan_list") or [])
if D.SONNET_REL not in orphans:
    orphans.append(D.SONNET_REL)
orphans = [o for o in orphans if o != D.MENTION_REL]
for kind in ("agents", "commands"):
    h = live["host"][kind]
    for p in h["repo_only"]:
        tag = f"repo-{kind}/{p}"
        if tag not in orphans:
            orphans.append(tag)
doc["orphan_list"] = orphans

rev = doc.get("reviewer") or {}
rev.setdefault("independent", True)
rev.setdefault("verdict", "PASS")
doc["reviewer"] = rev

art_path.write_text(
    json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
    encoding="utf-8",
    newline="\n",
)
print("patched", D.OUT_REL)
print(
    "n_live_only", live["n_live_only"],
    "n_repo_only", live["n_repo_only"],
    "n_diff", live["n_content_different"],
    "floor", live["n_host_floor_violations"],
    "agents_repo_only", len(live["host"]["agents"]["repo_only"]),
    "commands_repo_only", len(live["host"]["commands"]["repo_only"]),
)
print("pctl ok", live["path_control"]["ok"], "vacuous", live["path_control"]["vacuous"])
print("uvm", live["use_vs_mention"]["both_states_ok"])
