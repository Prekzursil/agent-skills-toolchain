#!/usr/bin/env python3
"""Build planted IMP-0038 trees and run the live reconciler."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import registration_fixture as fx  # noqa: E402
import registration_reconciler as rr  # noqa: E402

FIX = HERE / "fixtures" / "control"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_scenario(*, omit_forgotten: bool = False) -> dict:
    dest = FIX / ("gap" if omit_forgotten else "complete")
    dest.mkdir(parents=True, exist_ok=True)
    trees = fx.build_control_trees(
        dest, omit_forgotten_from_repo_manifest=omit_forgotten
    )
    before = rr.snapshot_tree(trees["live"])
    report = rr.reconcile(trees["repo"], trees["live"])
    after = rr.snapshot_tree(trees["live"])
    mutated = before != after
    planted_repo = [
        fx.PLANTED["repo_only_skill"],
        fx.PLANTED["repo_only_hook"],
        fx.PLANTED["repo_only_rule"],
        fx.PLANTED["repo_only_command"],
    ]
    planted_live = [
        fx.PLANTED["live_only_skill"],
        fx.PLANTED["live_only_hook"],
        fx.PLANTED["live_only_rule"],
        fx.PLANTED["live_only_command"],
    ]
    repo_ok = all(x in set(report["repo_only"]) for x in planted_repo)
    live_ok = all(x in set(report["live_only"]) for x in planted_live)
    shared_ok = all(
        x in set(report["in_both"])
        for x in (
            fx.PLANTED["shared_skill"],
            fx.PLANTED["shared_hook"],
            fx.PLANTED["shared_rule"],
            fx.PLANTED["shared_command"],
        )
    )
    return {
        "repo_root": str(trees["repo"]),
        "live_root": str(trees["live"]),
        "report": report,
        "live_mutated": mutated,
        "planted_repo_found": repo_ok,
        "planted_live_found": live_ok,
        "shared_not_in_diff": shared_ok,
        "no_auto_deploy": report["auto_deploy"] is False and not mutated,
        "in_sync_refused": report["in_sync"] is False,
        "live_only_measured": report["live_only_measured"] is True,
        "sets_agree": report["sets_agree"],
        "host_candidates": rr.host_candidates(REPO),
        "pass": repo_ok
        and live_ok
        and shared_ok
        and (not mutated)
        and report["auto_deploy"] is False
        and report["in_sync"] is False
        and report["live_only_measured"] is True
        and (report["sets_agree"] is True if not omit_forgotten else report["sets_agree"] is False),
    }


if __name__ == "__main__":
    out = run_scenario()
    printable = {k: out[k] for k in sorted(out) if k != "report"}
    printable["repo_only"] = out["report"]["repo_only"]
    printable["live_only"] = out["report"]["live_only"]
    print(json.dumps(printable, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0038-scenario" if out["pass"] else "FAILED:IMP-0038-scenario")
    raise SystemExit(0 if out["pass"] else 1)
