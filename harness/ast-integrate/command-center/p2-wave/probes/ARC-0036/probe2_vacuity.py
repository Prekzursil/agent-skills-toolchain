#!/usr/bin/env python3
"""Probe 2: vacuity delete-after-success, exit-zero-alone, uncaught mutation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import cases as C  # noqa: E402
import schema_bind as SB  # noqa: E402

ART = REPO / "command-center/phase3/A5/TEST-PLAN.json"


def resolve_anchor(rel: str, line: int, snippet: str) -> tuple[bool, str]:
    path = REPO / rel
    if not path.is_file():
        return False, f"missing:{rel}"
    lines = path.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        return False, f"line-oob:{rel}:{line}"
    if snippet not in lines[line - 1]:
        return False, f"snippet-miss:{rel}:{line}"
    return True, f"{rel}:{line}"


def main() -> int:
    live = C.run_all()
    vac = live["vacuity"]
    print(
        f"vacuity_before={vac['before_verdict']} after={vac['after_verdict']} "
        f"flipped={vac['flipped']} c2_after={vac['c2_after']}"
    )
    print(f"exit_zero_alone={live['exit_zero_alone']['verdict']}")
    if not vac["flipped"] or vac["c2_after"] != "UNSATISFIED":
        print("FAILED:ARC-0036-probe2 vacuity did not flip on C2")
        return 1
    if live["exit_zero_alone"]["verdict"] == "COMPLETE":
        print("FAILED:ARC-0036-probe2 exit-zero-alone was COMPLETE")
        return 1

    if not ART.is_file():
        print("FAILED:ARC-0036-probe2 TEST-PLAN.json missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    body = SB.payload(doc)
    if "SUCCESS:ARC-0036" not in text:
        print("FAILED:ARC-0036-probe2 sentinel absent")
        return 1

    schema_errs = SB.errors(doc)
    if schema_errs:
        print("FAILED:ARC-0036-probe2 schema", schema_errs[0])
        return 1
    for g in ({}, {"state": "SUCCESS"}, {"blob": "x" * 2000}):
        if not SB.errors(g):
            print("FAILED:ARC-0036-probe2 schema accepted garbage")
            return 1
    print("schema_ok=True garbage_rejected=True")

    art_vac = None
    for m in body.get("mutations") or doc.get("mutations") or []:
        if m.get("id") == "MUT-VACUITY-DELETE-ARTIFACT":
            art_vac = m
            break
    if not art_vac or art_vac.get("flipped") is not True:
        print("FAILED:ARC-0036-probe2 artifact vacuity row missing or not flipped")
        return 1
    if art_vac.get("expected_complete") is not False:
        print("FAILED:ARC-0036-probe2 vacuity expected_complete must be false")
        return 1
    if art_vac.get("live_after") != vac["after_verdict"]:
        print("FAILED:ARC-0036-probe2 vacuity after-verdict drift")
        return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        print("FAILED:ARC-0036-probe2 reviewer is not independent")
        return 1
    uncaught = body.get("mutation_suite_would_not_catch") or rev.get(
        "mutation_suite_would_not_catch"
    ) or {}
    uid = str(uncaught.get("id") or "")
    if len(uid) < 3 or len(str(uncaught.get("why_uncaught") or "")) < 24:
        print("FAILED:ARC-0036-probe2 reviewer did not name an uncaught mutation")
        return 1
    suite_obj = body.get("suite") or doc.get("suite") or {}
    suite_ids = {c.get("id") for c in suite_obj.get("cases") or []}
    mut_ids = {m.get("id") for m in (body.get("mutations") or doc.get("mutations") or [])}
    if uid in suite_ids or uid in mut_ids:
        print(f"FAILED:ARC-0036-probe2 uncaught id {uid} is already in the suite")
        return 1
    print(f"uncaught={uid}")

    anchors = body.get("live_anchors") or []
    if not anchors:
        print("FAILED:ARC-0036-probe2 live_anchors missing")
        return 1
    dossier = 0
    live_n = 0
    for i, row in enumerate(anchors):
        rel = str(row.get("path") or "")
        line = int(row.get("line") or 0)
        snippet = str(row.get("snippet") or "")
        ok, why = resolve_anchor(rel, line, snippet)
        print(f"anchor[{i}] ok={ok} {why}")
        if not ok:
            print("FAILED:ARC-0036-probe2 unresolved anchor")
            return 1
        kind = str(row.get("kind") or "")
        if kind == "dossier":
            dossier += 1
        elif kind == "live-tree":
            live_n += 1
        else:
            print(f"FAILED:ARC-0036-probe2 bad evidence kind {kind}")
            return 1
    if live_n < 4:
        print(f"FAILED:ARC-0036-probe2 evidence live-tree count {live_n}")
        return 1

    print("SUCCESS:ARC-0036-probe2 vacuity exit-zero uncaught-mutation anchors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
