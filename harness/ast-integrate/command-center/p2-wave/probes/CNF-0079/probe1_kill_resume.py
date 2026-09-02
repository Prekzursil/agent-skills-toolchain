#!/usr/bin/env python3
"""Named probe 1: three SIGKILL boundaries vs uninterrupted artifact hash.

Re-runs the live kill/resume suite. Does not trust the confirmation file's
hashes without recomputing them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import experiment as E  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0079-resume-parity.json"
SENTINEL_PREFIX = "SUCCESS:CNF-0079"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0079-probe1 confirmation artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0079":
        print("FAILED:CNF-0079-probe1 unit_id", doc.get("unit_id"))
        return 1
    blob = json.dumps(doc)
    if SENTINEL_PREFIX not in blob or SENTINEL_PREFIX not in str(doc.get("sentinel") or ""):
        print("FAILED:CNF-0079-probe1 sentinel absent")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0079-probe1 self-declared", doc.get("state"))
        return 1

    suite = E.run_suite()
    kills = suite["kills"]
    if len(kills) != 3:
        print(f"FAILED:CNF-0079-probe1 kill_points={len(kills)} want=3")
        return 1
    recorded = {row["id"]: row for row in (doc.get("comparisons") or [])}
    failed = []
    for row in kills:
        if not row["pass"]:
            failed.append(row["id"] + ":live-fail")
            continue
        got = recorded.get(row["id"])
        if not got:
            failed.append(row["id"] + ":missing-in-artifact")
            continue
        if got.get("left_sha256") != row["left_sha256"]:
            failed.append(row["id"] + ":left-sha-drift")
        if got.get("right_sha256") != row["right_sha256"]:
            failed.append(row["id"] + ":right-sha-drift")
        if got.get("equivalent") is not True:
            failed.append(row["id"] + ":artifact-not-equivalent")
        if got.get("side_effect_replay"):
            failed.append(row["id"] + ":artifact-claims-replay")
        if list(got.get("skipped_on_resume") or []) != row["skipped_on_resume"]:
            failed.append(row["id"] + ":skip-drift")
    if failed:
        print("FAILED:CNF-0079-probe1", failed)
        print(json.dumps([{k: v for k, v in r.items() if k != "checkpoint_at_kill"} for r in kills], indent=2)[:4000])
        return 1
    if doc.get("kill_points_exercised") != 3:
        print("FAILED:CNF-0079-probe1 kill_points_exercised", doc.get("kill_points_exercised"))
        return 1
    out = {
        "probe": "probe1-kill-resume",
        "unit_id": "CNF-0079",
        "kill_points": [r["kill_after"] for r in kills],
        "uninterrupted_sha256": suite["clean"]["artifact_sha256"],
        "all_equivalent": True,
        "side_effect_replay": False,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    for row in kills:
        print(
            f"kill {row['kill_after']} equivalent={row['equivalent']} "
            f"skipped={row['skipped_on_resume']} executed={row['executed_on_resume']} "
            f"replay={row['side_effect_replay']}"
        )
    print("SUCCESS:CNF-0079-probe1 three kill-point resume parity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
