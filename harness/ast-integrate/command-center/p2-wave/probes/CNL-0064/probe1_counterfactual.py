#!/usr/bin/env python3
"""Probe 1: every weighted fixture has an equal-weight counterfactual; flips flagged."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import tabulate as T  # noqa: E402
from fixtures_lib import councils  # noqa: E402

ART_REL = (
    "command-center/design/council/"
    "CNL-0064-weighted-voting-weight-provenance-and-post-hoc-audit.md"
)
SCHEMA_REL = "command-center/p2-wave/probes/CNL-0064/note.schema.json"


def _excess(delta: dict) -> str:
    return str(
        delta.get("excess_weight_on_weighted_winner")
        or delta.get("excess_weight_on_weighted_winner")
        or ""
    )


def main() -> int:
    art = REPO / ART_REL
    if not art.is_file() or art.stat().st_size <= 0:
        print("FAILED:CNL-0064-probe1 design note missing")
        return 1
    text = art.read_text(encoding="utf-8")
    try:
        note = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:CNL-0064-probe1 unparseable:{exc}")
        return 1
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(note)
    if str(note.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:CNL-0064-probe1 self-declared {note.get('state')}")
        return 1
    if "SUCCESS:CNL-0064" not in text:
        print("FAILED:CNL-0064-probe1 sentinel-absent")
        return 1

    recorded = {row["id"]: row for row in (note.get("fixture_results") or [])}
    live_rows = []
    for fid, fixture in councils().items():
        live = T.decide(fixture)
        rec = recorded.get(fid)
        if fixture.get("expect_reject"):
            if not live.get("rejected"):
                print(f"FAILED:CNL-0064-probe1 {fid} should reject")
                return 1
            if rec is None or not rec.get("rejected"):
                print(f"FAILED:CNL-0064-probe1 {fid} note omitted rejection")
                return 1
            live_rows.append(
                {"id": fid, "rejected": True, "code": live.get("reject_code")}
            )
            continue
        if live.get("rejected"):
            print(f"FAILED:CNL-0064-probe1 {fid} unexpected reject {live}")
            return 1
        if fixture.get("weighted") and "equal_weight_counterfactual" not in live:
            print(f"FAILED:CNL-0064-probe1 {fid} live CF missing")
            return 1
        expect_flip = bool(fixture.get("expect_flip"))
        if bool(live.get("weighting_flip")) != expect_flip:
            print(
                f"FAILED:CNL-0064-probe1 {fid} flip live={live.get('weighting_flip')} "
                f"expect={expect_flip}"
            )
            return 1
        if rec is None:
            print(f"FAILED:CNL-0064-probe1 {fid} missing from design note")
            return 1
        if rec.get("weighting_flip") != live.get("weighting_flip"):
            print(f"FAILED:CNL-0064-probe1 {fid} note/live flip mismatch")
            return 1
        if rec.get("weighted_winner") != live["weighted_result"]["winner"]:
            print(f"FAILED:CNL-0064-probe1 {fid} weighted winner drift")
            return 1
        if rec.get("equal_winner") != live["equal_weight_counterfactual"]["winner"]:
            print(f"FAILED:CNL-0064-probe1 {fid} equal winner drift")
            return 1
        if fixture.get("weighted") and rec.get("equal_weight_counterfactual") is None:
            print(f"FAILED:CNL-0064-probe1 {fid} note omitted CF")
            return 1
        live_rows.append(
            {
                "id": fid,
                "weighted_winner": live["weighted_result"]["winner"],
                "equal_winner": live["equal_weight_counterfactual"]["winner"],
                "weighting_flip": live["weighting_flip"],
                "excess": _excess(live["weighting_delta"]),
            }
        )

    weighted_n = sum(
        1
        for f in councils().values()
        if f.get("weighted") and not f.get("expect_reject")
    )
    flagged = [r for r in live_rows if r.get("weighting_flip")]
    if weighted_n < 2:
        print("FAILED:CNL-0064-probe1 need >=2 weighted fixtures")
        return 1
    if len(flagged) < 2:
        print("FAILED:CNL-0064-probe1 need >=2 flip fixtures")
        return 1

    out = {
        "probe": "probe1-counterfactual",
        "unit_id": "CNL-0064",
        "weighted_fixtures": weighted_n,
        "flips_flagged": len(flagged),
        "rows": live_rows,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"weighted={weighted_n} flips={len(flagged)} "
        f"ids={[r['id'] for r in live_rows]}"
    )
    print("SUCCESS:CNL-0064-probe1 equal-weight counterfactual and flip flags")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
