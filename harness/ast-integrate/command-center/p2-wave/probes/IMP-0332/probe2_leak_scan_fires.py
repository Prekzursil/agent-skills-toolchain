#!/usr/bin/env python3
"""Named probe 2: leak one ranking; the delivered-prompt scan FIRES.

Known-present runs first (detector control). A fresh clean session must
then be SILENT. Aggregation is recomputed in this file from raw ballots
with a local Borda loop (does not read session.aggregation).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from council.protocol.ngt import scan_delivered_prompts  # noqa: E402
from scenario import load_fixture, run_session  # noqa: E402


def local_borda(catalog_ids: list[str], rankings: dict[str, list[str]]) -> dict[str, int]:
    n = len(catalog_ids)
    scores = {idea_id: 0 for idea_id in catalog_ids}
    for ranking in rankings.values():
        for place, idea_id in enumerate(ranking):
            scores[idea_id] += n - place
    return scores


def main() -> int:
    fixture = load_fixture()
    leak = fixture["leak"]

    planted = run_session(leak=leak, midstream_rank=True)
    planted_session = planted["session"]
    planted_scan = scan_delivered_prompts(planted_session, before_aggregation=True)
    if not planted_scan["fired"]:
        print(
            "FAILED:IMP-0332-probe2 planted leak did not fire "
            f"scan={planted_scan}"
        )
        return 1
    hits = planted_scan["findings"]
    if not any(
        f.get("source_id") == leak["source"] and f.get("recipient_id") == leak["dest"]
        for f in hits
    ):
        print(
            "FAILED:IMP-0332-probe2 fire was not attributed to leaked pair "
            f"source={leak['source']} dest={leak['dest']} findings={hits}"
        )
        return 1

    clean = run_session(leak=None, midstream_rank=True)
    clean_session = clean["session"]
    clean_scan = scan_delivered_prompts(clean_session, before_aggregation=True)
    if clean_scan["fired"]:
        print(
            "FAILED:IMP-0332-probe2 clean session fired "
            f"findings={clean_scan['findings']}"
        )
        return 1

    result = clean_session.aggregate()
    raw = clean_session.raw_ballots()
    ids = clean_session.catalog_ids()
    local = local_borda(ids, raw)
    if local != result["scores"]:
        print(
            "FAILED:IMP-0332-probe2 independent local Borda mismatch "
            f"session={result['scores']} local={local}"
        )
        return 1

    planted_after_open = scan_delivered_prompts(planted_session, before_aggregation=True)
    if not planted_after_open["fired"]:
        print("FAILED:IMP-0332-probe2 planted findings vanished before aggregation")
        return 1

    doc = {
        "probe": "probe2-leak-scan-fires",
        "unit_id": "IMP-0332",
        "pass": True,
        "known_present_run_first": True,
        "planted_fired": True,
        "planted_reason_id": planted_scan["reason_id"],
        "planted_finding_count": len(hits),
        "leak_source": leak["source"],
        "leak_dest": leak["dest"],
        "clean_fired": False,
        "independent_borda_match": True,
        "scores": result["scores"],
        "order": result["order"],
        "detector_control": {
            "known_present_run_first": True,
            "fired_before_absence_reported": True,
        },
    }
    print(json.dumps(doc, sort_keys=True))
    print(
        f"planted_fired=True clean_fired=False leak={leak['source']}->{leak['dest']} "
        f"borda_match=True"
    )
    print("SUCCESS:IMP-0332-probe2 leak one ranking; prompt scan FIRES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
