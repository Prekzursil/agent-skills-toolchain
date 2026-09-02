#!/usr/bin/env python3
"""Probe 1: published set-difference matches a live recompute and is empty.

Does not trust the artifact's preserved boolean alone. Re-extracts dissent
ids from the resolved scorecards and from MINORITY-REPORT.json, recomputes
scorecard_ids - report_ids, and requires the published lists to match.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402

ART = REPO / "command-center/phase3/MINORITY-REPORT.json"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0071-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("MINORITY-REPORT.json missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:ARC-0071" not in text:
        return fail("sentinel absent")

    resolved = E.resolve_inputs(REPO)
    sc_rows = E.extract_dissents(resolved["scorecards"])
    rp_rows = E.extract_report_positions(doc)
    live = E.preservation_diff(
        E.id_set(sc_rows),
        E.id_set(rp_rows),
        scorecard_source=resolved["scorecards_path"],
        report_source="command-center/phase3/MINORITY-REPORT.json",
    )
    pub = doc.get("preservation") or {}
    if not isinstance(pub.get("scorecard_minus_report"), list):
        return fail("published scorecard_minus_report is not a computed list")
    if pub.get("formula") != "missing = scorecard_ids - report_ids":
        return fail("published formula missing or narrated")
    if pub.get("scorecard_source") == pub.get("report_source"):
        return fail("published computation is a tautology")
    if live["scorecard_dissent_ids"] != pub.get("scorecard_dissent_ids"):
        return fail("published scorecard ids != live extract")
    if live["report_dissent_ids"] != pub.get("report_dissent_ids"):
        return fail("published report ids != live extract")
    if live["scorecard_minus_report"] != pub.get("scorecard_minus_report"):
        return fail("published missing list != live difference")
    if live["missing_count"] != 0 or not live["preserved"]:
        return fail(f"live missing={live['scorecard_minus_report']}")
    if len(sc_rows) < 1:
        return fail("no recorded dissents extracted")

    ir = doc.get("input_resolution") or {}
    live_sc_exists = (REPO / E.LIVE_SCORECARDS).is_file()
    if bool(ir.get("scorecards_live")) != live_sc_exists:
        return fail("scorecards_live flag does not match disk")
    if ir.get("scorecards_path") != resolved["scorecards_path"]:
        return fail("artifact scorecards_path != resolver")
    if not live_sc_exists:
        lowered = text.lower()
        if "nine live architectures were scored" in lowered:
            return fail("overclaim: nine live architectures")
        if ir.get("scorecards_live") is True:
            return fail("claimed live scorecards that are absent")

    judge = resolved["reviewer_judge_id"]
    rev = E.undistorted(sc_rows, rp_rows, judge)
    if not rev["undistorted"]:
        return fail(f"reviewer {judge} distorted or missing {rev}")
    if not (doc.get("reviewer") or {}).get("was_dissenting_judge"):
        return fail("reviewer was_dissenting_judge not true")

    losing = [r for r in sc_rows if r["entry_id"] != resolved["winner_entry_id"]]
    if losing:
        lose_ids = {r["dissent_id"] for r in losing}
        if lose_ids - E.id_set(rp_rows):
            return fail("losing-entry dissent dropped from report")

    print(
        json.dumps(
            {
                "scorecard_count": live["scorecard_count"],
                "report_count": live["report_count"],
                "missing": live["scorecard_minus_report"],
                "preserved": live["preserved"],
                "scorecards_live": resolved["scorecards_live"],
                "reviewer_undistorted": True,
                "reviewer_judge_id": judge,
            },
            sort_keys=True,
        )
    )
    print(
        f"missing={live['scorecard_minus_report']} "
        f"n={live['scorecard_count']} live_sc={resolved['scorecards_live']}"
    )
    print("SUCCESS:ARC-0071-probe1 set-difference empty and published")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
