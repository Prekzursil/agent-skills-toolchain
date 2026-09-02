#!/usr/bin/env python3
"""Probe 2: diversity assertion computed from the seated roster.

The seated panel must meet the vendor-diversity minimum declared in
JUDGE-PANEL.json. A single-vendor mutant of the same roster must FAIL.
The independence reviewer must not be a judge or a dossier author.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402
import diversity as D  # noqa: E402
import panel_spec as S  # noqa: E402

PANEL = REPO / "command-center" / "phase3" / "JUDGE-PANEL.json"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0066-probe2 {msg}")
    return 1


def main() -> int:
    if not PANEL.is_file():
        return fail("JUDGE-PANEL.json absent")
    doc = json.loads(PANEL.read_text(encoding="utf-8"))
    payload = S.panel_payload(doc)
    roster = payload.get("seated_panel") or []
    decision = payload.get("decision") or {}
    if len(roster) != int(decision.get("panel_size") or 0):
        return fail(
            f"roster_size={len(roster)} panel_size={decision.get('panel_size')}"
        )
    declared = int(decision.get("vendor_diversity_minimum") or 0)
    model_min = int(decision.get("model_diversity_minimum") or 0)
    if declared < 2:
        return fail(f"declared vendor_diversity_minimum={declared}")
    live = D.diversity_report(roster, declared, model_min)
    print(
        f"live vendors={live['vendors']} count={live['vendor_count']} "
        f"minimum={declared} ok={live['ok']}"
    )
    print(
        f"live models={live['models']} count={live['model_count']} "
        f"minimum={model_min} model_ok={live['model_ok']}"
    )
    if not live["ok"]:
        return fail("seated panel fails declared diversity minimum")

    mutant = copy.deepcopy(roster)
    for judge in mutant:
        judge["vendor"] = "anthropic"
        judge["model"] = "opus"
    bad = D.diversity_report(mutant, declared, model_min)
    print(
        f"mutant vendors={bad['vendors']} count={bad['vendor_count']} "
        f"ok={bad['ok']} (want False)"
    )
    if bad["ok"] or bad["vendor_count"] != 1:
        return fail("single-vendor mutant did not fail diversity")

    reviewer = doc.get("reviewer") or {}
    indep = payload.get("independence_review") or reviewer
    rid = reviewer.get("reviewer_id")
    judge_ids = {j.get("judge_id") for j in roster}
    bench_ids = {j.get("judge_id") for j in (payload.get("bench") or [])}
    if rid in judge_ids or rid in bench_ids:
        return fail(f"reviewer {rid} is a seated or bench judge")
    if rid != S.REVIEWER_ID:
        return fail(f"reviewer_id={rid} expected {S.REVIEWER_ID}")
    if reviewer.get("independent") is not True:
        return fail("reviewer.independent is not true")
    if indep.get("neither_judge_nor_dossier_author") is not True:
        return fail("reviewer did not certify neither-judge-nor-author")

    report = C.census()
    author_vendors = {
        C.norm((r.get("authorship") or {}).get("vendor"))
        for r in report["rows"]
        if r.get("present") and (r.get("authorship") or {}).get("vendor")
    }
    rv = C.norm(reviewer.get("vendor"))
    if rv and rv in author_vendors:
        return fail(f"reviewer vendor {rv} matches a dossier author {author_vendors}")

    phase3_roster = REPO / "command-center" / "phase3" / "ROSTER.json"
    roster_src = (payload.get("roster_source") or {}).get("present")
    disk_roster = phase3_roster.is_file()
    print(f"phase3_ROSTER.json present={disk_roster} recorded={roster_src}")
    if bool(roster_src) != disk_roster:
        return fail("roster_source.present disagrees with disk")

    print(
        "diversity_live_ok=True diversity_mutant_fails=True "
        "reviewer_independent=True computed_from_roster=True"
    )
    print("SUCCESS:ARC-0066-probe2 diversity assertion from roster")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
