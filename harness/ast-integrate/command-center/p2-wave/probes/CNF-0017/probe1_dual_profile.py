#!/usr/bin/env python3
"""Probe 1: empty fresh home, identical command set, both profiles, outcome diff."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0017-fresh-profile-repro.json"
SENTINEL = "SUCCESS:CNF-0017 emitted only when the artifact at output_path exists"


def main() -> int:
    run = S.run_scenario()
    print(f"fresh_empty_at_start={run['homes']['fresh']['empty_at_start']}")
    print(f"identical_command_set={run['identical_command_set']}")
    print(f"n_commands={len(run['command_set'])}")
    print(f"local_state_dependent={run['local_state_dependent']}")
    print(f"survived_fresh_profile={run['survived_fresh_profile']}")
    if not run["homes"]["fresh"]["empty_at_start"]:
        print("FAILED:CNF-0017-probe1 fresh home not empty at start")
        return 1
    if not run["identical_command_set"]:
        print("FAILED:CNF-0017-probe1 command sets diverged")
        return 1
    if len(run["command_set"]) < 8:
        print("FAILED:CNF-0017-probe1 command set too small")
        return 1
    argv_loaded = [tuple(r["argv"]) for r in run["failures"]]
    argv_set = [tuple(c["argv"]) for c in run["command_set"]]
    if argv_loaded != argv_set:
        print("FAILED:CNF-0017-probe1 per-failure argv drifted from command_set")
        return 1
    if not run["local_state_dependent"] or not run["survived_fresh_profile"]:
        print("FAILED:CNF-0017-probe1 both-states control missing")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0017-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    view = S.artifact_view(doc)
    if view.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0017-probe1 self-declared {view.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:CNF-0017-probe1 sentinel absent")
        return 1
    diff = view.get("outcome_diff") or {}
    if diff.get("attached") is not True or diff.get("identical_command_set") is not True:
        print("FAILED:CNF-0017-probe1 outcome_diff not attached")
        return 1
    art_cmds = [c.get("id") for c in (view.get("command_set") or [])]
    live_cmds = [c["id"] for c in run["command_set"]]
    if art_cmds != live_cmds:
        print("FAILED:CNF-0017-probe1 artifact command_set != live")
        return 1
    if set(diff.get("local_state_dependent") or []) != set(run["local_state_dependent"]):
        print("FAILED:CNF-0017-probe1 local-state set drift")
        return 1
    ev = view.get("evidence") if isinstance(view.get("evidence"), dict) else {}
    fresh_ok = (
        view.get("fresh_empty_at_start") is True
        or (isinstance(ev, dict) and ev.get("fresh_empty_at_start") is True)
    )
    if not fresh_ok:
        print("FAILED:CNF-0017-probe1 evidence listing not empty")
        return 1
    print("SUCCESS:CNF-0017-probe1 dual-profile identical commands and outcome diff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
