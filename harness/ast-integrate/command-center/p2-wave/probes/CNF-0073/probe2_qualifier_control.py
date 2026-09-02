#!/usr/bin/env python3
"""Probe 2: dropped-hedge control + same-path-rerun refusal + independent re-derive.

Reviewer is given the raw inventory spans and live probe output first, then
compares to the artifact conclusion. Reading the conclusion first does not count.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from audit import load_inventory, payload, recheck_row  # noqa: E402
from translate import PATH_RECORDED, SamePathRerun, run_second_path  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0073-multilingual-recheck.json"


def main() -> int:
    inv = load_inventory()
    derived = [recheck_row(c) for c in inv["citations"]]
    planted = [r for r in derived if r.get("planted_control") == "dropped-hedge"]
    if not planted:
        print("FAILED:CNF-0073-probe2 no planted dropped-hedge rows")
        return 1
    for row in planted:
        q = row["qualifier_diff"]
        print(
            f"planted {row['id']} dropped={q['dropped_by_recorded']} "
            f"material={q['material_change']} survives={row['claim_survives']} "
            f"verdict={row['verdict']}"
        )
        if not q["material_change"] or not q["dropped_by_recorded"]:
            print(f"FAILED:CNF-0073-probe2 planted {row['id']} did not file dropped hedge")
            return 1
        if not row["claim_survives"]:
            print(f"FAILED:CNF-0073-probe2 planted {row['id']} headline should still survive")
            return 1
        if row["verdict"] != "PARTIAL":
            print(f"FAILED:CNF-0073-probe2 planted {row['id']} want PARTIAL got {row['verdict']}")
            return 1

    survive = [r for r in derived if r.get("planted_control") is None]
    if not survive or any(r["qualifier_diff"]["material_change"] for r in survive):
        print("FAILED:CNF-0073-probe2 survive-control did not stay material_change=false")
        return 1

    try:
        run_second_path(planted[0]["original_span"], planted[0]["language"], PATH_RECORDED, PATH_RECORDED)
        print("FAILED:CNF-0073-probe2 same-path-rerun was accepted")
        return 1
    except SamePathRerun as exc:
        print(f"same-path-rerun rejected classification={exc.classification}")

    if not ART.is_file():
        print("FAILED:CNF-0073-probe2 artifact missing (derived first, then compared)")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    body = payload(doc)
    by_id = {r["id"]: r for r in body.get("citations") or []}
    for row in derived:
        art = by_id.get(row["id"])
        if not art:
            print(f"FAILED:CNF-0073-probe2 artifact missing {row['id']}")
            return 1
        if art.get("verdict") != row["verdict"]:
            print(f"FAILED:CNF-0073-probe2 verdict drift {row['id']}")
            return 1
        if art["qualifier_diff"]["dropped_by_recorded"] != row["qualifier_diff"]["dropped_by_recorded"]:
            print(f"FAILED:CNF-0073-probe2 qualifier drift {row['id']}")
            return 1
    protocol = body.get("reviewer_protocol") or {}
    reviewer = doc.get("reviewer") or {}
    if protocol.get("shown_conclusion_first") is not False:
        print("FAILED:CNF-0073-probe2 reviewer was anchored")
        return 1
    if reviewer.get("independent") is not True or protocol.get("independent") is not True:
        print("FAILED:CNF-0073-probe2 reviewer not independent")
        return 1
    ctrls = {c["id"]: c for c in body.get("controls") or []}
    if not ctrls.get("dropped-hedge", {}).get("fired"):
        print("FAILED:CNF-0073-probe2 artifact dropped-hedge control not fired")
        return 1
    if not ctrls.get("same-path-rerun", {}).get("fired"):
        print("FAILED:CNF-0073-probe2 artifact same-path-rerun control not fired")
        return 1
    print("reviewer_rederived_before_conclusion=True")
    print("SUCCESS:CNF-0073-probe2 qualifier control same-path-rerun")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
