#!/usr/bin/env python3
"""Probe 1: planted both-direction sets + no auto-deploy.

DETECTOR CONTROL: a known repo-only skill and a known live-only skill must
both be found before any in-sync verdict. The live tree mtime/hash census
must be unchanged (report, do not deploy).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0038.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    run = S.run_scenario(omit_forgotten=False)
    rec = run["report"]
    summary = {
        "planted_repo_found": run["planted_repo_found"],
        "planted_live_found": run["planted_live_found"],
        "shared_not_in_diff": run["shared_not_in_diff"],
        "no_auto_deploy": run["no_auto_deploy"],
        "in_sync_refused": run["in_sync_refused"],
        "live_only_measured": run["live_only_measured"],
        "sets_agree": run["sets_agree"],
        "repo_only": rec["repo_only"],
        "live_only": rec["live_only"],
        "live_tree_mutated": rec["live_tree_mutated"],
        "auto_deploy": rec["auto_deploy"],
    }
    print(json.dumps(summary, sort_keys=True))
    if not run["pass"]:
        print("FAILED:IMP-0038-probe1 detector control did not fire both directions")
        return 1
    if rec["live_tree_mutated"] or rec["writes"]:
        print("FAILED:IMP-0038-probe1 live tree was written (auto-deploy)")
        return 1
    if not ART.is_file():
        print("FAILED:IMP-0038-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print(f"FAILED:IMP-0038-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0038" not in text:
        print("FAILED:IMP-0038-probe1 sentinel-absent")
        return 1
    live_repo = set(rec["repo_only"])
    live_live = set(rec["live_only"])
    meas = doc.get("measurement") or {}
    art_repo = set(meas.get("repo_only") or [])
    art_live = set(meas.get("live_only") or [])
    if art_repo != live_repo or art_live != live_live:
        print(
            "FAILED:IMP-0038-probe1 receipt sets != live reconcile "
            f"receipt_repo={sorted(art_repo)} live_repo={sorted(live_repo)} "
            f"receipt_live={sorted(art_live)} live_live={sorted(live_live)}"
        )
        return 1
    if meas.get("auto_deploy") is not False:
        print("FAILED:IMP-0038-probe1 receipt did not record auto_deploy=false")
        return 1
    if meas.get("live_only_measured") is not True:
        print("FAILED:IMP-0038-probe1 receipt did not record live_only_measured")
        return 1
    print(
        f"planted_repo={run['planted_repo_found']} planted_live={run['planted_live_found']} "
        f"no_deploy={run['no_auto_deploy']} in_sync={rec['in_sync']}"
    )
    print("SUCCESS:IMP-0038-probe1 both-direction detector control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
