#!/usr/bin/env python3
"""Probe 1: enumerate hooks/skills from RUNNING client processes, classify diffs."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import observe_healthy  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cnf0100-p1-") as tmp:
        obs = observe_healthy(Path(tmp))

    clients = obs["clients"]
    if len(clients) != 2:
        print(f"FAILED:CNF-0100-probe1 expected 2 clients got {len(clients)}")
        return 1
    for c in clients:
        if not c["running_at_observation"]:
            print(f"FAILED:CNF-0100-probe1 {c['name']} not running when enumerated")
            return 1
        if c["inventory_source"] != "running-process":
            print(f"FAILED:CNF-0100-probe1 {c['name']} inventory not from process")
            return 1
        if not c["nonce_pid_match"]:
            print(f"FAILED:CNF-0100-probe1 {c['name']} pid mismatch vs inventory file")
            return 1
        if not c["hooks"] and c["name"] == "cursor":
            print("FAILED:CNF-0100-probe1 cursor loaded zero hooks on healthy install")
            return 1
        if not c["skills"]:
            print(f"FAILED:CNF-0100-probe1 {c['name']} loaded zero skills")
            return 1

    diffs = obs["set_difference"]
    if obs["unclassified_count"] != 0:
        print("FAILED:CNF-0100-probe1 unclassified set-difference entries")
        return 1
    if any(not d.get("classification") for d in diffs):
        print("FAILED:CNF-0100-probe1 a difference lacks classification")
        return 1
    if not diffs:
        print("FAILED:CNF-0100-probe1 expected declared SessionStart/composer diffs")
        return 1
    if any(d["classification"] == "defect" for d in diffs):
        print("FAILED:CNF-0100-probe1 healthy install produced unclassified defect")
        print(json.dumps(diffs, indent=2)[:2000])
        return 1

    by_name = {c["name"]: c for c in clients}
    cursor_hooks = set(by_name["cursor"]["hooks"])
    codex_hooks = set(by_name["codex"]["hooks"])
    if "SessionStart:hook.session-start" not in cursor_hooks:
        print("FAILED:CNF-0100-probe1 cursor missing SessionStart (read-from-file?)")
        return 1
    if "SessionStart:hook.session-start" in codex_hooks:
        print("FAILED:CNF-0100-probe1 codex unexpectedly loaded SessionStart")
        return 1
    if "skill.cursor-composer" not in set(by_name["cursor"]["skills"]):
        print("FAILED:CNF-0100-probe1 cursor missing composer skill")
        return 1
    if "skill.cursor-composer" in set(by_name["codex"]["skills"]):
        print("FAILED:CNF-0100-probe1 codex loaded cursor-only skill")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1_running_inventory",
                "clients": [
                    {
                        "name": c["name"],
                        "pid": c["pid"],
                        "hooks_n": len(c["hooks"]),
                        "skills_n": len(c["skills"]),
                    }
                    for c in clients
                ],
                "set_difference_n": len(diffs),
                "unclassified_count": 0,
                "every_difference_classified": True,
                "inventories_read_from_running_processes": True,
            },
            indent=2,
        )
    )
    print("SUCCESS:CNF-0100-probe1 running-process inventories classified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
