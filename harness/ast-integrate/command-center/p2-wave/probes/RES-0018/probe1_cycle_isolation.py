#!/usr/bin/env python3
"""Named probe 1: isolation + per-command filesystem diffs (census signal)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import SENTINEL, run_full_cycle  # noqa: E402

ART = REPO / "command-center" / "research" / "RES-0018.json"
REQUIRED = ("install", "update", "repair", "rollback", "uninstall")


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:RES-0018-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "RES-0018":
        print("FAILED:RES-0018-probe1 unit_id", doc.get("unit_id"))
        return 1
    if SENTINEL not in text:
        print("FAILED:RES-0018-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0018-probe1 self-declared", doc.get("state"))
        return 1

    with tempfile.TemporaryDirectory(prefix="res0018-p1-") as tmp:
        cycle = run_full_cycle(Path(tmp))

    iso = cycle["isolation"]
    if not iso["isolated"] or not iso["proven_before_first_command"]:
        print("FAILED:RES-0018-probe1 isolation", json.dumps(iso, indent=2)[:1500])
        return 1
    if not cycle["live_profile_unchanged_after_cycle"]:
        print("FAILED:RES-0018-probe1 live profile mutated")
        return 1

    names = [s["command"] for s in cycle["commands"]]
    if names != list(REQUIRED):
        print("FAILED:RES-0018-probe1 command order", names)
        return 1

    for step in cycle["commands"]:
        if step["file_change_count"] < 1:
            print("FAILED:RES-0018-probe1 empty filesystem diff", step["command"])
            return 1
        if not step["live_profile_unchanged"]:
            print("FAILED:RES-0018-probe1 live touched by", step["command"])
            return 1
        if step["claude_json_gained_enabled_plugins"]:
            print("FAILED:RES-0018-probe1 enabledPlugins leaked into .claude.json")
            return 1

    install = cycle["commands"][0]
    enabled = [k for k in install["settings_keys_created"] if "enabledPlugins" in k]
    if not enabled:
        print("FAILED:RES-0018-probe1 install did not create enabledPlugins key")
        return 1

    orphan = cycle["orphan"]
    if orphan["verdict"] != "NO_INHERIT" or orphan["reinstall_inherited_prior_marker"]:
        print("FAILED:RES-0018-probe1 orphan inherit", orphan)
        return 1
    if not orphan["marker_present_before_uninstall"]:
        print("FAILED:RES-0018-probe1 marker missing before uninstall")
        return 1

    art_cmds = [c.get("command") for c in (doc.get("per_command_diffs") or [])]
    if art_cmds != list(REQUIRED):
        print("FAILED:RES-0018-probe1 artifact command map", art_cmds)
        return 1

    payload = {
        "probe": "probe1-cycle-isolation",
        "unit_id": "RES-0018",
        "isolated_before_first_command": True,
        "live_unchanged": True,
        "commands": names,
        "file_change_counts": {s["command"]: s["file_change_count"] for s in cycle["commands"]},
        "key_change_counts": {s["command"]: s["key_change_count"] for s in cycle["commands"]},
        "orphan_verdict": orphan["verdict"],
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "isolated=True live_unchanged=True commands="
        + ",".join(names)
        + f" orphan={orphan['verdict']}"
    )
    print("SUCCESS:RES-0018-probe1 isolation and per-command filesystem diffs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
