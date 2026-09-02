#!/usr/bin/env python3
"""Named probe 2: same-base-model-twice is NOT vendor-diverse.

Both-states:
  BAD  two seats sharing base_model claude-opus -> FIRE (vendor_diverse=False)
  GOOD anthropic/claude-opus + openai/gpt-4o -> SILENT (vendor_diverse=True)

Second signal (different mechanism): Counter over the fixture JSON
base_model field, without calling vendor_diversity_report.

Also: schema garbage rejection so the declared contract is not vacuous.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from mechanism import (  # noqa: E402
    ROSTER_DIVERSE,
    ROSTER_SAME_BASE_CROSS_VENDOR,
    ROSTER_SAME_BASE_TWICE,
    ROSTER_SAME_VENDOR_DIFF_MODEL,
    independent_model_recount,
    seating_decision,
    vendor_diversity_report,
)

ART = REPO / (
    "command-center/design/council/"
    "CNL-0018-model-and-vendor-diversity-selection-under-a-real-quota-ce.md"
)
SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"
FIX = HERE / "fixtures" / "declared.json"

GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)


def _field_counter(roster: list[dict], field: str) -> Counter:
    return Counter(str(s.get(field) or "").strip().lower() for s in roster)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNL-0018-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNL-0018":
        print("FAILED:CNL-0018-probe2 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:CNL-0018" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNL-0018-probe2 sentinel-absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNL-0018-probe2 self-declared", doc.get("state"))
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    rejected = 0
    for g in GARBAGE:
        try:
            jsonschema.Draft7Validator(schema).validate(g)
        except jsonschema.ValidationError:
            rejected += 1
    if rejected != 3:
        print(f"FAILED:CNL-0018-probe2 schema vacuous rejected={rejected}/3")
        return 1

    declared = json.loads(FIX.read_text(encoding="utf-8"))
    fx_bad = declared["rosters"]["same_base_twice"]
    fx_good = declared["rosters"]["diverse"]
    fx_cross = declared["rosters"]["same_base_cross_vendor"]

    r_bad = vendor_diversity_report(ROSTER_SAME_BASE_TWICE)
    r_good = vendor_diversity_report(ROSTER_DIVERSE)
    r_cross = vendor_diversity_report(ROSTER_SAME_BASE_CROSS_VENDOR)
    r_same_v = vendor_diversity_report(ROSTER_SAME_VENDOR_DIFF_MODEL)

    if r_bad.get("vendor_diverse") is not False or not r_bad.get("same_base_model_twice"):
        print("FAILED:CNL-0018-probe2 same-base-twice not flagged")
        print(json.dumps(r_bad, indent=2))
        return 1
    if r_good.get("vendor_diverse") is not True:
        print("FAILED:CNL-0018-probe2 diverse roster not accepted")
        print(json.dumps(r_good, indent=2))
        return 1
    if r_cross.get("vendor_diverse") is not False or not r_cross.get("same_base_model_twice"):
        print("FAILED:CNL-0018-probe2 cross-vendor same-base not flagged")
        print(json.dumps(r_cross, indent=2))
        return 1
    if r_same_v.get("vendor_diverse") is not False:
        print("FAILED:CNL-0018-probe2 same-vendor different-model accepted")
        return 1

    # Independent recount over fixture JSON (not the Python constants).
    json_counts_bad = _field_counter(fx_bad, "base_model")
    json_counts_good = _field_counter(fx_good, "base_model")
    json_dup_bad = [m for m, n in json_counts_bad.items() if n >= 2]
    json_dup_good = [m for m, n in json_counts_good.items() if n >= 2]
    py_recount_bad = independent_model_recount(ROSTER_SAME_BASE_TWICE)
    if not json_dup_bad:
        print("FAILED:CNL-0018-probe2 JSON recount missed duplicate")
        return 1
    if json_dup_good:
        print("FAILED:CNL-0018-probe2 JSON recount false-duplicate on GOOD")
        return 1
    if py_recount_bad.get("duplicates") != sorted(json_dup_bad):
        print(
            "FAILED:CNL-0018-probe2 signal disagreement "
            f"py={py_recount_bad.get('duplicates')} json={sorted(json_dup_bad)}"
        )
        return 1
    if json_counts_cross := [m for m, n in _field_counter(fx_cross, "base_model").items() if n >= 2]:
        if "gpt-4o" not in json_counts_cross:
            print("FAILED:CNL-0018-probe2 cross-vendor JSON recount")
            return 1
    else:
        print("FAILED:CNL-0018-probe2 cross-vendor JSON missed duplicate")
        return 1

    seat_m = seating_decision(ROSTER_SAME_BASE_TWICE, "high-stakes")
    seat_o = seating_decision(ROSTER_SAME_BASE_TWICE, "discovery")
    if seat_m.get("action") != "refuse":
        print("FAILED:CNL-0018-probe2 mandatory same-base was not refused")
        return 1
    if seat_o.get("action") != "seat-with-waiver":
        print("FAILED:CNL-0018-probe2 optional same-base was not waived")
        return 1

    recorded = doc.get("diversity_control") or {}
    if recorded.get("same_base_twice_flagged") is not True:
        print("FAILED:CNL-0018-probe2 artifact missing same_base_twice_flagged")
        return 1
    if recorded.get("diverse_accepted") is not True:
        print("FAILED:CNL-0018-probe2 artifact missing diverse_accepted")
        return 1
    if doc.get("answers", {}).get("mandatory_from_risk_tier") != "high-stakes":
        print("FAILED:CNL-0018-probe2 mandatory_from_risk_tier drift")
        return 1

    claims = doc.get("claims") or []
    not_checked = [c for c in claims if c.get("verdict") == "NOT-CHECKED"]
    if not not_checked:
        print("FAILED:CNL-0018-probe2 missing NOT-CHECKED quota claim")
        return 1

    verbatim = (
        "NEGATIVE CONTROL (diversity): the check FIRES on a same-base-model-twice "
        "roster (two claude-opus seats; vendor_diverse=false, "
        "same_base_model_twice=true, reason=same-base-model-twice) and is SILENT "
        "on the known-good roster (anthropic/claude-opus + openai/gpt-4o; "
        "vendor_diverse=true). It also FIRES on openai/gpt-4o + azure/gpt-4o "
        "(distinct vendor labels, same base model) so vendor-string makeup "
        "cannot game the metric."
    )
    out = {
        "probe": "probe2-same-base-model",
        "unit_id": "CNL-0018",
        "same_base_twice_flagged": True,
        "diverse_accepted": True,
        "cross_vendor_same_base_flagged": True,
        "schema_garbage_rejected": rejected,
        "json_duplicate_base_models": json_dup_bad,
        "mandatory_refuse": seat_m["action"],
        "optional_waiver": seat_o["action"],
        "pass": True,
        "negative_control_verbatim": verbatim,
    }
    print(json.dumps(out, sort_keys=True))
    print(verbatim)
    print("SUCCESS:CNL-0018-probe2 same-base-model both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
