#!/usr/bin/env python3
"""Probe 2: both-states missing-commit detector.

Bad state: required file untracked in developer tree → clone fails.
Good state: same file committed → clone passes.
Hand-copy of the untracked file into the clone is the missing-commit proof.
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


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cnf0030-p2-") as tmp:
        pair = C.live_pair(Path(tmp))
    missing = pair["missing"]
    control = pair["control"]
    bad_ok = (
        missing["developer"]["exit_code"] == 0
        and missing["clone"]["exit_code"] != 0
        and missing["hand_copy"]["exit_code"] == 0
        and C.MISSING_FILE in missing["untracked_developer"]
        and C.MISSING_FILE not in missing["untracked_clone"]
    )
    good_ok = (
        control["developer"]["exit_code"] == 0
        and control["clone"]["exit_code"] == 0
        and C.MISSING_FILE not in control["untracked_developer"]
    )
    print(
        json.dumps(
            {
                "probe": "probe2-missing-commit",
                "unit_id": "CNF-0030",
                "bad_developer_exit": missing["developer"]["exit_code"],
                "bad_clone_exit": missing["clone"]["exit_code"],
                "hand_copy_exit": missing["hand_copy"]["exit_code"],
                "good_developer_exit": control["developer"]["exit_code"],
                "good_clone_exit": control["clone"]["exit_code"],
                "untracked_developer": missing["untracked_developer"],
                "untracked_clone": missing["untracked_clone"],
                "fired_on_untracked": bad_ok,
                "silent_on_committed": good_ok,
            },
            sort_keys=True,
        )
    )
    if not bad_ok:
        print("FAILED:CNF-0030-probe2 untracked required file did not fail the clone")
        return 1
    if not good_ok:
        print("FAILED:CNF-0030-probe2 committed control failed; detector always-red")
        return 1
    if not pair["identical_command_both_trees"]:
        print("FAILED:CNF-0030-probe2 commands were not identical")
        return 1

    if not ART.is_file():
        print("FAILED:CNF-0030-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    findings = {f.get("id"): f for f in (doc.get("findings") or []) if isinstance(f, dict)}
    f1 = findings.get("F1-untracked-required-payload") or {}
    f2 = findings.get("F2-committed-required-payload") or {}
    if f1.get("passes_developer_fails_clone") is not True:
        print("FAILED:CNF-0030-probe2 artifact F1 not recorded as missing-commit")
        return 1
    if f1.get("hand_copy_makes_clone_pass") is not True:
        print("FAILED:CNF-0030-probe2 artifact F1 hand-copy flag false")
        return 1
    if f2.get("passes_developer_fails_clone") is not False:
        print("FAILED:CNF-0030-probe2 artifact F2 should be green in both trees")
        return 1
    inv = doc.get("untracked_inventory") or []
    if not any(
        isinstance(row, dict) and "required_payload.txt" in (row.get("paths") or [])
        for row in inv
    ):
        print("FAILED:CNF-0030-probe2 artifact untracked inventory missing payload")
        return 1
    print("SUCCESS:CNF-0030-probe2 missing-commit detector both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
