#!/usr/bin/env python3
"""Probe 1: planted duplicate, novel module, git-history deleted symbol.

Strike-1 token/export search must miss the renamed plant. Normalized
shingles must catch it as DUPLICATE-OF the salvaged tools/lib module.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import census as C  # noqa: E402
import git_fixture as G  # noqa: E402
import mechanism as M  # noqa: E402

ART = REPO / "command-center" / "receipts" / "BLD-0033.json"


def main() -> int:
    git_repo = G.build_history_repo()
    try:
        doc = C.fixture_census(git_repo)
    finally:
        shutil.rmtree(git_repo, ignore_errors=True)

    ctrl = doc["controls"]
    for name in (
        "planted_duplicate",
        "novel_no_false_positive",
        "git_history_deleted_symbol",
    ):
        row = ctrl[name]
        print(f"{name} result={row['result']} {json.dumps({k: v for k, v in row.items() if k != 'result'}, sort_keys=True)}")
        if row["result"] != "PASS":
            print(f"FAILED:BLD-0033-probe1 {name}")
            return 1

    planted = next(e for e in doc["entries"] if str(e["subject_path"]).endswith("task-journal.mjs"))
    if planted["filename_same"]:
        print("FAILED:BLD-0033-probe1 filename drove duplicate (must be mechanism)")
        return 1
    if planted["score"] < M.DUPLICATE_THRESHOLD:
        print("FAILED:BLD-0033-probe1 planted score below duplicate threshold")
        return 1
    if not ctrl["planted_duplicate"]["token_search_missed_rename"]:
        print("FAILED:BLD-0033-probe1 token search should miss renamed exports")
        return 1

    novel = next(
        e
        for e in doc["entries"]
        if str(e["subject_path"]).endswith("geodesic-bounce-scheduler.mjs")
    )
    if novel["verdict"] != "GENUINELY-NEW":
        print("FAILED:BLD-0033-probe1 novel not GENUINELY-NEW")
        return 1
    if not doc["surfaces_complete"]:
        print("FAILED:BLD-0033-probe1 fixture surfaces incomplete")
        return 1

    if ART.is_file():
        rec = json.loads(ART.read_text(encoding="utf-8"))
        if rec.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:BLD-0033-probe1 artifact self-declared {rec.get('state')}")
            return 1
        if "SUCCESS:BLD-0033" not in ART.read_text(encoding="utf-8"):
            print("FAILED:BLD-0033-probe1 sentinel absent")
            return 1
        ac = rec.get("controls") or {}
        for name in (
            "planted_duplicate",
            "novel_no_false_positive",
            "git_history_deleted_symbol",
        ):
            if (ac.get(name) or {}).get("result") != "PASS":
                print(f"FAILED:BLD-0033-probe1 artifact control {name}")
                return 1

    print("SUCCESS:BLD-0033-probe1 planted-duplicate novel git-history")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
