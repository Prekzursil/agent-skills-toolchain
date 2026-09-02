#!/usr/bin/env python3
"""Probe 2: independent re-check of every absent case + receipt consistency."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classifier as C  # noqa: E402
import harvest as H  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "CNF-0164.json"


def main() -> int:
    if not RECEIPT.is_file():
        print("FAILED:CNF-0164-probe2 receipt missing")
        return 1
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    cases = doc.get("cases") or []
    if not isinstance(cases, list) or len(cases) < 4:
        print("FAILED:CNF-0164-probe2 cases missing")
        return 1

    live = {row["id"]: row for row in H.harvest_all() if row.get("id")}
    disagreements: list[str] = []
    absent_ids: list[str] = []
    reviewer_absent_ok = 0

    for case in cases:
        cid = str(case.get("id") or "")
        quote = str(case.get("quote") or "")
        src = str(case.get("source_path") or "")
        claimed = str(case.get("class") or "")
        primary = C.classify_quote(quote, src)
        reviewer = C.reviewer_classify_quote(quote, src)
        print(
            f"case {cid} claimed={claimed} primary={primary['class']} "
            f"reviewer={reviewer['class']}"
        )
        if primary["class"] != claimed:
            disagreements.append(f"{cid}: receipt={claimed} live-primary={primary['class']}")
        if reviewer["class"] != claimed:
            disagreements.append(
                f"{cid}: receipt={claimed} reviewer={reviewer['class']}"
            )
        if claimed == "absent":
            absent_ids.append(cid)
            if reviewer["class"] != "absent":
                disagreements.append(f"{cid}: reviewer refused absent")
            else:
                reviewer_absent_ok += 1
        if cid.startswith("CTRL-") or cid.startswith("CTRL"):
            planted = live.get(cid)
            if planted and planted.get("expect") and planted["expect"] != claimed:
                disagreements.append(
                    f"{cid}: planted expect={planted['expect']} claimed={claimed}"
                )

    rec_absents = [str(x.get("id") or "") for x in (doc.get("absent_cases") or [])]
    if sorted(rec_absents) != sorted(absent_ids):
        disagreements.append(
            f"absent_cases list mismatch receipt={rec_absents} cases={absent_ids}"
        )

    reviewer_doc = doc.get("reviewer") or {}
    rec_rechecked = [str(x) for x in (reviewer_doc.get("rechecked_absent_ids") or [])]
    if sorted(rec_rechecked) != sorted(absent_ids):
        disagreements.append("reviewer.rechecked_absent_ids does not cover every absent")
    if reviewer_doc.get("independent") is not True:
        disagreements.append("reviewer.independent is not true")
    if str(reviewer_doc.get("verdict") or "") != "PASS":
        disagreements.append("reviewer.verdict is not PASS")
    if reviewer_doc.get("disagreements"):
        disagreements.append("receipt reviewer listed disagreements")

    if "SUCCESS:CNF-0164" not in RECEIPT.read_text(encoding="utf-8"):
        disagreements.append("sentinel SUCCESS:CNF-0164 absent from receipt")

    if disagreements:
        print("FAILED:CNF-0164-probe2")
        for d in disagreements:
            print(" ", d)
        return 1

    print(
        f"reviewer_rechecked_absents={reviewer_absent_ok} "
        f"absent_n={len(absent_ids)} cases={len(cases)}"
    )
    print("SUCCESS:CNF-0164-probe2 independent absent re-check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
