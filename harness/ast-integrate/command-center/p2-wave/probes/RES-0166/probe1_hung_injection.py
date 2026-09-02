#!/usr/bin/env python3
"""Probe 1: hung-worker injection arm + metric instruments.

Independent of probe 2 (which re-hashes Goose lineage). Runs the live
comparison, refuses a happy-path-only decision, and requires the artifact
to record the injection arm.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / E.ARTIFACT_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0166-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    art = json.loads(ART.read_text(encoding="utf-8"))
    if art.get("unit_id") != E.UNIT:
        return fail(f"unit_id {art.get('unit_id')}")
    if E.SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    st = str(art.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    live = E.run_comparison()
    if live["happy_path_only_is_complete_comparison"] is True:
        return fail("engine marked happy-path-only complete")
    if not live["rankings_differ"]:
        return fail("hung injection did not change winner")
    if live["happy_winner"] == live["hung_winner"]:
        return fail("winners equal despite ranking list differ?")

    hung_rows = {r["topology"]: r for r in live["arms"]["hung_injection"]["rows"]}
    happy_rows = {r["topology"]: r for r in live["arms"]["happy"]["rows"]}
    if hung_rows["flat"]["recovery_from_hung_worker"] != 0.0:
        return fail("flat hung recovery must be 0")
    if hung_rows["lead-worker"]["recovery_from_hung_worker"] != 1.0:
        return fail("lead-worker hung recovery must be 1")
    if hung_rows["tree"]["recovery_from_hung_worker"] != 1.0:
        return fail("tree hung recovery must be 1")
    if hung_rows["hierarchical-fanin"]["recovery_from_hung_worker"] != 0.0:
        return fail("hierarchical-fanin hung recovery must be 0")
    def task_complete(row: dict, tid: str) -> bool:
        for item in row.get("tasks") or []:
            if item.get("task_id") == tid:
                return item.get("complete") is True
        return False

    if not task_complete(hung_rows["flat"], "T-FAIL2"):
        return fail("T-FAIL2 must complete on flat (same-worker retry)")
    if not task_complete(hung_rows["lead-worker"], "T-FAIL2"):
        return fail("T-FAIL2 must complete on lead-worker")
    for topo in E.TOPOLOGIES:
        if happy_rows[topo]["recovery_from_hung_worker"] is not None:
            return fail(f"{topo} happy arm must not report hung recovery")
        if happy_rows[topo]["all_complete"] is not True:
            return fail(f"{topo} happy arm not all-complete")

    metrics = art.get("metrics") or []
    ids = [m.get("id") for m in metrics if isinstance(m, dict)]
    need = {
        "time_to_first_finding",
        "total_distinct_findings",
        "deadlock_rate",
        "token_cost",
        "recovery_from_hung_worker",
    }
    if set(ids) != need:
        return fail(f"metrics {ids}")
    for m in metrics:
        if not m.get("instrument") or not m.get("known_failure_mode"):
            return fail(f"metric {m.get('id')} missing instrument or failure mode")

    arm = art.get("hung_worker_injection_arm") or {}
    if arm.get("required") is not True:
        return fail("hung arm not required")
    if arm.get("happy_path_only_is_complete_comparison") is not False:
        return fail("artifact accepts happy-path-only")
    if sorted(arm.get("tasks") or []) != sorted(E.HUNG_TASK_IDS):
        return fail(f"hung tasks {arm.get('tasks')}")

    topos = [t.get("id") for t in (art.get("topologies") or [])]
    if topos != list(E.TOPOLOGIES):
        return fail(f"topologies {topos}")

    task_ids = [t.get("id") for t in (art.get("task_set") or [])]
    if task_ids != [t["id"] for t in E.TASKS]:
        return fail(f"task_set {task_ids}")

    cmp_ = art.get("comparison") or {}
    if cmp_.get("happy_winner") != live["happy_winner"]:
        return fail("happy_winner drift")
    if cmp_.get("hung_winner") != live["hung_winner"]:
        return fail("hung_winner drift")
    if cmp_.get("rankings_differ") is not True:
        return fail("artifact rankings_differ not true")
    if cmp_.get("happy_path_only_is_complete_comparison") is not False:
        return fail("comparison accepts happy-path-only")

    art_hung = (cmp_.get("hung_injection_rows") or {}).get("flat") or {}
    if art_hung.get("recovery_from_hung_worker") != 0.0:
        return fail("artifact flat hung recovery drift")

    mutant = deepcopy(art)
    mutant["hung_worker_injection_arm"]["required"] = False
    mutant["comparison"]["happy_path_only_is_complete_comparison"] = True
    mutant["comparison"]["hung_winner"] = mutant["comparison"]["happy_winner"]
    if mutant["comparison"]["happy_path_only_is_complete_comparison"] is not True:
        return fail("mutant setup failed")
    if E.mutant_happy_path_only_accepted(live) is not True:
        return fail("planted happy-path-only mutant was not detectable")

    print(
        json.dumps(
            {
                "probe": "probe1-hung-injection",
                "happy_winner": live["happy_winner"],
                "hung_winner": live["hung_winner"],
                "flat_hung_recovery": hung_rows["flat"]["recovery_from_hung_worker"],
                "tree_hung_recovery": hung_rows["tree"]["recovery_from_hung_worker"],
                "fail2_flat": task_complete(hung_rows["flat"], "T-FAIL2"),
                "metrics": ids,
            },
            sort_keys=True,
        )
    )
    print(
        f"happy={live['happy_winner']} hung={live['hung_winner']} "
        f"flat_rec=0 tree_rec=1 fail2_flat=True mutant_red=True"
    )
    print("SUCCESS:RES-0166-probe1 hung-worker injection arm and happy-path control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
