#!/usr/bin/env python3
"""Named probe 2: independence, honesty, condition-13 canary, reviewer resample.

Independence: the receipt must not cite a prior-lane sidecar as evidence.
Honesty: NOT-CHECKED / FALSE must not be folded into GO.
Condition 13: a canary-success detector exists, and under PR-ONLY a canary
cannot exist as written.
Reviewer: re-probe five conditions including at least one NOT-CHECKED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import evaluate as E  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0187.json"
BANNED_EVIDENCE = (
    "PHASE-GRAPH.json",
    "phase-graph.json",
    "command-center/PHASE-GRAPH.json",
)
RESAMPLE = (1, 4, 12, 13, 15)  # includes NOT-CHECKED on this tree plus C13


def _evidence_blobs(doc: dict) -> list[str]:
    blobs: list[str] = []
    payload = E.gate_payload(doc)
    for row in payload.get("conditions") or []:
        if not isinstance(row, dict):
            continue
        for key in ("evidence_path", "evidence", "cited_from", "inherited_from"):
            val = row.get(key)
            if isinstance(val, str):
                blobs.append(val)
            elif isinstance(val, list):
                blobs.extend(str(x) for x in val)
    for ev in doc.get("evidence") or []:
        if isinstance(ev, dict):
            blobs.append(str(ev.get("path") or ev.get("anchor") or ""))
        elif isinstance(ev, str):
            blobs.append(ev)
    indep = payload.get("independence") if isinstance(payload.get("independence"), dict) else {}
    blobs.append(json.dumps(indep))
    return blobs


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0187-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0187" not in json.dumps(doc):
        print("FAILED:CNF-0187-probe2 sentinel absent")
        return 1

    payload = E.gate_payload(doc)
    indep = payload.get("independence") if isinstance(payload.get("independence"), dict) else {}
    if indep.get("prior_lane_sidecar_consulted") is not False:
        print("FAILED:CNF-0187-probe2 sidecar consulted flag")
        return 1
    if indep.get("prior_lane_sidecar_cited_as_evidence") is not False:
        print("FAILED:CNF-0187-probe2 sidecar cited flag")
        return 1
    for blob in _evidence_blobs(doc):
        for banned in BANNED_EVIDENCE:
            if banned in blob:
                print(f"FAILED:CNF-0187-probe2 cited {banned} as evidence")
                return 1

    rows = payload.get("conditions") or []
    if len(rows) != 21:
        print(f"FAILED:CNF-0187-probe2 rows={len(rows)}")
        return 1
    ids = [int(r.get("id") or 0) for r in rows if isinstance(r, dict)]
    if ids != list(range(1, 22)):
        print("FAILED:CNF-0187-probe2 ids not 1..21", ids)
        return 1

    if payload.get("overall_verdict") == "GO":
        print("FAILED:CNF-0187-probe2 GO on a tree with unsatisfied conditions")
        return 1
    not_true = [r for r in rows if r.get("verdict") != "TRUE"]
    if not not_true:
        print("FAILED:CNF-0187-probe2 all-TRUE on this sparse tree is overclaim")
        return 1
    nc = [r for r in rows if r.get("verdict") == "NOT-CHECKED"]
    for r in nc:
        exp = r.get("settling_experiment") or ""
        if len(str(exp)) < 12:
            print(f"FAILED:CNF-0187-probe2 NOT-CHECKED C{r.get('id')} missing experiment")
            return 1

    c13 = next(r for r in rows if r.get("id") == 13)
    if c13.get("verdict") != "FALSE":
        print("FAILED:CNF-0187-probe2 C13 must be FALSE as written, not upgraded", c13)
        return 1
    if c13.get("canary_possible_under_pr_only") is not False:
        print("FAILED:CNF-0187-probe2 C13 did not report canary impossible under PR-ONLY")
        return 1
    good13 = E.eval_c13(E.world_good())
    broken13 = E.eval_c13(E.world_broken())
    if good13["verdict"] != "TRUE" or broken13["verdict"] != "FALSE":
        print("FAILED:CNF-0187-probe2 C13 both-states", good13, broken13)
        return 1
    routing = payload.get("condition_13_owner_routing") or {}
    if not routing.get("decision_needed"):
        print("FAILED:CNF-0187-probe2 C13 not routed to owner")
        return 1

    live = {r["id"]: r for r in E.evaluate_world(E.build_live_world(REPO))}
    resampled = []
    for cid in RESAMPLE:
        art = next(r for r in rows if r.get("id") == cid)
        now = live[cid]
        if art.get("verdict") != now["verdict"]:
            print(f"FAILED:CNF-0187-probe2 resample C{cid} {art.get('verdict')} vs {now['verdict']}")
            return 1
        resampled.append({"id": cid, "verdict": now["verdict"]})
    if not any(x["verdict"] == "NOT-CHECKED" for x in resampled):
        print("FAILED:CNF-0187-probe2 resample missing NOT-CHECKED", resampled)
        return 1

    for r in rows:
        dc = r.get("detector_control") or {}
        if dc.get("fired_on_broken") is not True or dc.get("silent_on_good") is not True:
            print(f"FAILED:CNF-0187-probe2 detector C{r.get('id')} {dc}")
            return 1

    summary = {
        "independence_ok": True,
        "overall": payload.get("overall_verdict"),
        "not_true": len(not_true),
        "not_checked": len(nc),
        "c13_owner_routed": True,
        "resampled": resampled,
    }
    print(json.dumps(summary, default=str))
    print("SUCCESS:CNF-0187-probe2 independence honesty canary-13 reviewer-resample")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
