#!/usr/bin/env python3
"""Probe 1: re-derive clone SHA == fix SHA and identical command, then check the artifact.

Runs the committed-file control live FIRST so the verdict is not anchored on the
artifact conclusion. Then requires the artifact to record the same contract.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import clone_compare as C  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0030-fresh-clone-confirm.json"
SENTINEL = (
    "SUCCESS:CNF-0030 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the clone SHA equals the "
    "fix SHA and both trees ran the identical command. Any other terminal "
    "state is FAILED:CNF-0030 <classification> with the diagnostic tail attached."
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cnf0030-p1-") as tmp:
        control = C.scenario_committed_control(Path(tmp))
        missing = C.scenario_untracked_required(Path(tmp) / "also")

    live_equal = control["clone_sha_equals_fix_sha"] and missing["clone_sha_equals_fix_sha"]
    cmd_ok = (
        control["developer"]["command"]
        == control["clone"]["command"]
        == missing["developer"]["command"]
        == missing["clone"]["command"]
    )
    both_green = (
        control["developer"]["exit_code"] == 0 and control["clone"]["exit_code"] == 0
    )
    print(
        json.dumps(
            {
                "probe": "probe1-clone-sha",
                "unit_id": "CNF-0030",
                "live_control_fix_sha": control["fix_sha"],
                "live_control_clone_sha": control["clone_sha"],
                "live_missing_fix_sha": missing["fix_sha"],
                "live_missing_clone_sha": missing["clone_sha"],
                "live_sha_equal": live_equal,
                "live_identical_command": cmd_ok,
                "live_control_both_green": both_green,
                "command": control["developer"]["command"],
            },
            sort_keys=True,
        )
    )
    if not live_equal:
        print("FAILED:CNF-0030-probe1 live clone SHA != fix SHA")
        return 1
    if not cmd_ok:
        print("FAILED:CNF-0030-probe1 live commands diverged")
        return 1
    if not both_green:
        print("FAILED:CNF-0030-probe1 committed control was not green in both trees")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0030-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:CNF-0030-probe1 catalog sentinel absent")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0030-probe1 self-declared {doc.get('state')}")
        return 1
    if doc.get("unit_id") != "CNF-0030":
        print("FAILED:CNF-0030-probe1 unit_id mismatch")
        return 1
    if doc.get("clone_sha_equals_fix_sha") is not True:
        print("FAILED:CNF-0030-probe1 artifact clone_sha_equals_fix_sha not true")
        return 1
    if doc.get("identical_command_both_trees") is not True:
        print("FAILED:CNF-0030-probe1 artifact identical_command_both_trees not true")
        return 1
    if doc.get("clone_sha") != doc.get("fix_sha"):
        print("FAILED:CNF-0030-probe1 artifact clone_sha != fix_sha")
        return 1
    if not isinstance(doc.get("clone_sha"), str) or len(doc["clone_sha"]) != 40:
        print("FAILED:CNF-0030-probe1 artifact sha not 40 hex")
        return 1
    if doc.get("command") != control["developer"]["command"]:
        print("FAILED:CNF-0030-probe1 artifact command drifted from live")
        return 1
    print("SUCCESS:CNF-0030-probe1 clone SHA equals fix SHA; identical command both trees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
