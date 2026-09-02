#!/usr/bin/env python3
"""Probe 1: family census + per-record executable schedule, counted mechanically.

Independent of the author's prose: re-parse the catalog question, recount the
fixture FORECASTING rows, and require both to equal expected n. Then require a
schedule verdict for every family member. Re-tabulation disagreement blocks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import family as F  # noqa: E402
import runtime as R  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/CNL-0043-executable-runtime-semantics-for-the-5-forecasting-protoco.md"
)
UNIT = "CNL-0043"


def main() -> int:
    cen = F.census()
    print(json.dumps({k: cen[k] for k in sorted(cen) if k != "ok"}, default=str)[:3500])
    if not cen["ok"]:
        print("FAILED:CNL-0043-probe1 census disagreement", cen["disagreements"])
        return 1
    if cen["expected_n"] != 5 or cen["family"] != "FORECASTING":
        print("FAILED:CNL-0043-probe1 expected family/n mismatch")
        return 1
    if cen["signal2_fixture"]["total_records_including_distractors"] <= 5:
        print("FAILED:CNL-0043-probe1 fixture has no distractor; census may be vacuous")
        return 1
    qsnip = cen["signal1_catalog_named"]["snippet"]
    if "P33 prediction-tournament" not in qsnip or "P26 " in qsnip:
        print("FAILED:CNL-0043-probe1 catalog question anchor is not CNL-0043", qsnip[:180])
        return 1
    esnip = cen["evidence_snippet"]
    if "family=FORECASTING" not in esnip or "TRADECRAFT" in esnip:
        print("FAILED:CNL-0043-probe1 evidence anchor is not CNL-0043", esnip[:180])
        return 1
    table = R.family_schedule_table("FORECASTING")
    if table["n"] != cen["expected_n"]:
        print(
            f"FAILED:CNL-0043-probe1 schedule rows {table['n']} != family {cen['expected_n']}"
        )
        return 1
    if table["not_executable"]:
        print("FAILED:CNL-0043-probe1 NOT-EXECUTABLE", table["not_executable"])
        return 1
    if sorted(table["executable"]) != ["P33", "P34", "P35", "P36", "P37"]:
        print("FAILED:CNL-0043-probe1 executable id set", table["executable"])
        return 1
    for row in table["rows"]:
        if not row["as_written_missing"]:
            print(f"FAILED:CNL-0043-probe1 {row['id']} claimed as-written complete")
            return 1
        if "resolution_criterion" not in row["as_written_missing"]:
            print(f"FAILED:CNL-0043-probe1 {row['id']} as-written criterion not null")
            return 1
    scored = []
    blob = R.load_forecasts()
    good = [f for f in blob["forecasts"] if not f.get("planted_bad")]
    for f in good:
        s = R.score_forecast(f)
        if not s.get("scored"):
            print("FAILED:CNL-0043-probe1 known-good unscored", s)
            return 1
        scored.append(s)
    if len(scored) != 5:
        print("FAILED:CNL-0043-probe1 expected 5 scored known-good")
        return 1
    if not ART.is_file():
        print("FAILED:CNL-0043-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0043-probe1 self-declared {doc.get('state')}")
        return 1
    if f"SUCCESS:{UNIT}" not in text:
        print("FAILED:CNL-0043-probe1 sentinel absent")
        return 1
    art_n = int((doc.get("family_census") or {}).get("expected_n") or -1)
    if art_n != 5:
        print("FAILED:CNL-0043-probe1 artifact expected_n != 5")
        return 1
    art_ids = [p.get("id") for p in (doc.get("protocols") or [])]
    if sorted(art_ids) != ["P33", "P34", "P35", "P36", "P37"]:
        print("FAILED:CNL-0043-probe1 artifact protocol ids", art_ids)
        return 1
    if len(doc.get("protocols") or []) != table["n"]:
        print("FAILED:CNL-0043-probe1 artifact protocol count != mechanical family count")
        return 1
    print(
        f"family=FORECASTING n=5 named={cen['signal1_catalog_named']['count']} "
        f"fixture={cen['signal2_fixture']['count']} library_present="
        f"{cen['signal3_live_library']['present']} executable={table['executable']} "
        f"scored_good={len(scored)}"
    )
    print("SUCCESS:CNL-0043-probe1 family census and executable schedules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
