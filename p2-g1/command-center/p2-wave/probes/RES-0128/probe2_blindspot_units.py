#!/usr/bin/env python3
"""Probe 2: every blind spot is a draft work-unit, never prose.

Also checks the live RES-0128 artifact when present: 16x12 table,
sentinel, and draft-unit blind spots. A prose list must be rejected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from canon import SENTINEL  # noqa: E402
from coverage import (  # noqa: E402
    coverage_from_docs,
    is_draft_unit,
    load_emitted_records,
    ranked_blind_spots,
)

CORPUS = HERE / "fixtures" / "corpus"
PROSE = HERE / "fixtures" / "prose-blindspots.json"
LIVE = REPO / "command-center" / "research" / "RES-0128.json"
OUT = HERE / "probe2-blindspot-units.raw.json"


def main() -> int:
    loaded = load_emitted_records(sorted(CORPUS.glob("RES-FX-*.json")))
    docs = [(uid, doc) for uid, _p, doc, st in loaded if st == "parsed"]
    cov = coverage_from_docs(docs, expected_units=[u for u, _ in docs])
    spots = ranked_blind_spots(cov)

    prose = json.loads(PROSE.read_text(encoding="utf-8"))
    prose_ok = all(not is_draft_unit(x) for x in prose)

    payload: dict = {
        "probe": "probe2-blindspot-units",
        "unit_id": "RES-0128",
        "fixture_blind_spot_count": len(spots),
        "fixture_all_draft_units": all(is_draft_unit(s) for s in spots),
        "prose_list_rejected": prose_ok and isinstance(prose, list) and len(prose) >= 2,
        "live_present": LIVE.is_file(),
        "pass": False,
    }

    if not spots:
        payload["error"] = "fixture corpus produced zero blind spots"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:RES-0128-probe2 no-blind-spots")
        return 1
    if not all(is_draft_unit(s) for s in spots):
        payload["error"] = "a fixture blind spot is not a draft unit definition"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:RES-0128-probe2 prose-shaped-spot")
        return 1
    if any(isinstance(s, str) for s in spots):
        payload["error"] = "blind spot list contains a prose string"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:RES-0128-probe2 string-spot")
        return 1
    if not payload["prose_list_rejected"]:
        payload["error"] = "prose fixture was accepted as draft units"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:RES-0128-probe2 prose-not-rejected")
        return 1

    # Uncovered papers must appear as a draft unit, not a sentence.
    paper_spots = [
        s
        for s in spots
        if s.get("rank_key", {}).get("id") == "papers"
        and s.get("rank_key", {}).get("kind") == "source-class"
    ]
    if len(paper_spots) != 1 or paper_spots[0]["rank_key"]["cited_unit_count"] != 0:
        payload["error"] = "uncovered class 'papers' missing as a draft unit"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:RES-0128-probe2 papers-spot")
        return 1
    ranks = [s["rank"] for s in spots]
    if ranks != list(range(1, len(spots) + 1)):
        payload["error"] = f"ranks not dense 1..n: {ranks}"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:RES-0128-probe2 rank-density")
        return 1

    if LIVE.is_file():
        text = LIVE.read_text(encoding="utf-8")
        live = json.loads(text)
        payload["live_state"] = live.get("state")
        payload["live_class_rows"] = len((live.get("coverage_table") or {}).get("classes") or [])
        payload["live_mode_rows"] = len((live.get("coverage_table") or {}).get("modes") or [])
        live_spots = live.get("ranked_blind_spots") or []
        payload["live_blind_spot_count"] = len(live_spots)
        if live.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            payload["error"] = f"live artifact self-declared {live.get('state')}"
            OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            print(json.dumps(payload, sort_keys=True))
            print("FAILED:RES-0128-probe2 live-blocked")
            return 1
        if SENTINEL not in text:
            payload["error"] = "live artifact missing completion sentinel"
            OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            print(json.dumps(payload, sort_keys=True))
            print("FAILED:RES-0128-probe2 sentinel-absent")
            return 1
        if payload["live_class_rows"] != 16 or payload["live_mode_rows"] != 12:
            payload["error"] = "live coverage table is not 16 classes x 12 modes"
            OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            print(json.dumps(payload, sort_keys=True))
            print("FAILED:RES-0128-probe2 live-table-width")
            return 1
        if not live_spots or not all(is_draft_unit(s) for s in live_spots):
            payload["error"] = "live ranked_blind_spots is not a list of draft units"
            OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            print(json.dumps(payload, sort_keys=True))
            print("FAILED:RES-0128-probe2 live-spots")
            return 1
        # Live tree has zero emitted RES-0001..0127 records: every class/mode uncovered.
        live_cited = sum(
            int(r.get("unit_count") or 0)
            for r in (live.get("coverage_table") or {}).get("classes") or []
        )
        payload["live_class_citations_total"] = live_cited
        missing = live.get("units_missing_emitted") or []
        payload["live_missing_emitted"] = len(missing)
        if live.get("records_parsed") not in (0, None) and live_cited != 0:
            # Honest: if records exist, citations may be non-zero. If none, all zero.
            pass
        if int(live.get("records_parsed") or 0) == 0 and live_cited != 0:
            payload["error"] = "zero parsed records but non-zero class coverage"
            OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            print(json.dumps(payload, sort_keys=True))
            print("FAILED:RES-0128-probe2 vacuous-nonzero")
            return 1

    payload["pass"] = True
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:RES-0128-probe2 blind spots are draft unit definitions; "
        "prose list rejected"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
