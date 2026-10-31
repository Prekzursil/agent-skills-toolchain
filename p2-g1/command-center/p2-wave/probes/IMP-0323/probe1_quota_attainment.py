#!/usr/bin/env python3
"""Probe 1: detector-control first, then easy-set FPR, 20-run quota table.

Known-present (hard question converging in round 1 with unmet quotas) must
FIRE before any absence is reported. Easy-question control set must not be
flagged; FPR is a number. Quota-attainment at convergence is printed for
20 runs. Independent recount uses canonical_id sets, not the detector's
fired boolean.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from council.antifail.premature import detect  # noqa: E402
import fixtures as F  # noqa: E402

RAW = HERE / "probe1-quota-attainment.raw.json"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0323-probe1 {msg}")
    return 1


def recount(run: dict) -> tuple[int, int]:
    ideas = {str(x.get("canonical_id") or x.get("id")) for x in run.get("ideas") or []}
    objs = {
        str(x.get("canonical_id") or x.get("id")) for x in run.get("objections") or []
    }
    ideas.discard("None")
    objs.discard("None")
    return len(ideas), len(objs)


def main() -> int:
    F.dump_json()
    disk_hard = json.loads((F.FIXTURES / "hard-round1.json").read_text(encoding="utf-8"))
    mem_hard = F.hard_round1()

    ctrl_disk = detect(disk_hard)
    ctrl_mem = detect(mem_hard)
    print(
        f"detector_control id={ctrl_disk.get('id')} status={ctrl_disk['status']} "
        f"fired={ctrl_disk['fired']} round_recorded="
        f"{ctrl_disk['quota'].get('round_index_recorded')} "
        f"ideas={ctrl_disk['quota']['unique_ideas_attained']}/"
        f"{ctrl_disk['quota']['min_unique_ideas']} "
        f"objections={ctrl_disk['quota']['objections_attained']}/"
        f"{ctrl_disk['quota']['min_objections']}"
    )
    if ctrl_disk["status"] != "FIRE" or not ctrl_disk["fired"]:
        return _fail("known-present hard-round1 did not FIRE")
    if ctrl_mem["status"] != ctrl_disk["status"]:
        return _fail("dict/json disagree on hard-round1")
    if int(ctrl_disk["quota"].get("round_index_recorded") or 0) != 1:
        return _fail("hard-round1 is not round 1")
    if ctrl_disk["quota"]["quotas_met"]:
        return _fail("hard-round1 quotas unexpectedly met")

    easy = json.loads((F.FIXTURES / "easy-control.json").read_text(encoding="utf-8"))
    easy_fire = 0
    easy_rows = []
    for run in easy:
        report = detect(run)
        if report["fired"]:
            easy_fire += 1
        n_i, n_o = recount(run)
        if n_i != report["quota"]["unique_ideas_attained"]:
            return _fail(f"idea recount mismatch {run['id']}")
        if n_o != report["quota"]["objections_attained"]:
            return _fail(f"objection recount mismatch {run['id']}")
        if report["status"] != "SILENT":
            return _fail(f"easy {run['id']} status={report['status']}")
        easy_rows.append(
            {
                "id": run["id"],
                "round_index": run["round_index"],
                "fired": report["fired"],
                "unique_ideas_attained": n_i,
                "objections_attained": n_o,
                "min_unique_ideas": run["divergence"]["min_unique_ideas"],
                "min_objections": run["divergence"]["min_objections"],
            }
        )
    fpr = easy_fire / len(easy)
    print(
        f"easy_control_n={len(easy)} easy_flagged={easy_fire} "
        f"false_positive_rate={fpr}"
    )
    if easy_fire != 0:
        return _fail(f"easy-question FPR {fpr} is not 0")

    twenty = json.loads((F.FIXTURES / "twenty-runs.json").read_text(encoding="utf-8"))
    if len(twenty) != 20:
        return _fail(f"twenty-runs length {len(twenty)}")
    table = []
    for run in twenty:
        report = detect(run)
        n_i, n_o = recount(run)
        want_fire = not (
            n_i >= run["divergence"]["min_unique_ideas"]
            and n_o >= run["divergence"]["min_objections"]
        )
        if bool(report["fired"]) != bool(want_fire):
            return _fail(
                f"{run['id']} fired={report['fired']} want_fire={want_fire} "
                f"ideas={n_i}/{run['divergence']['min_unique_ideas']} "
                f"obj={n_o}/{run['divergence']['min_objections']}"
            )
        row = {
            "id": run["id"],
            "label": run["label"],
            "round_index": run["round_index"],
            "min_unique_ideas": run["divergence"]["min_unique_ideas"],
            "min_objections": run["divergence"]["min_objections"],
            "unique_ideas_attained": n_i,
            "objections_attained": n_o,
            "fired": report["fired"],
            "status": report["status"],
            "decision_basis": report["decision_basis"],
        }
        table.append(row)
        print(
            f"run {run['id']} round={run['round_index']} "
            f"ideas={n_i}/{run['divergence']['min_unique_ideas']} "
            f"obj={n_o}/{run['divergence']['min_objections']} "
            f"status={report['status']}"
        )

    padded = next(r for r in table if r["id"] == "hard-padded-dups")
    if padded["unique_ideas_attained"] != 1:
        return _fail("padded duplicates were counted as distinct ideas")
    if not padded["fired"]:
        return _fail("padded duplicate run did not FIRE")

    late_unmet = [r for r in table if r["id"].startswith("hard-late-unmet")]
    if len(late_unmet) != 2 or any(not r["fired"] for r in late_unmet):
        return _fail("late unmet-quota runs must FIRE")
    if any(r["round_index"] <= 1 for r in late_unmet):
        return _fail("late unmet fixtures are not late")

    still = detect(json.loads((F.FIXTURES / "not-converged.json").read_text(encoding="utf-8")))
    missing = detect(
        json.loads((F.FIXTURES / "undeclared-quotas.json").read_text(encoding="utf-8"))
    )
    if still["status"] != "NOT-CHECKED" or missing["status"] != "NOT-CHECKED":
        return _fail("open or undeclared runs must be NOT-CHECKED")

    doc = {
        "detector_control_fired": True,
        "easy_control_n": len(easy),
        "easy_flagged": easy_fire,
        "false_positive_rate": fpr,
        "hard_round1_fired": True,
        "n_runs": 20,
        "pass": True,
        "quota_table": table,
        "easy_rows": easy_rows,
        "not_converged_status": still["status"],
        "undeclared_status": missing["status"],
        "padded_unique_ideas": padded["unique_ideas_attained"],
    }
    RAW.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"twenty_runs=20 fpr={fpr} hard_round1=FIRE "
        f"late_unmet_fire={len(late_unmet)}"
    )
    print("SUCCESS:IMP-0323-probe1 quota-attainment both-states FPR")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
