#!/usr/bin/env python3
"""Probe 2: planted unit on an unanswered question appears in proceeding-on-default.

Coverage: every catalog owner_question plus every packet question appears exactly
once. Independent reviewer: five ANSWERED control rows resolve the question;
five live catalog-marked ANSWERED rows lack an owner utterance path:line.
Schema mutant with closure_table removed must go red.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import closure as C  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0017.json"
SCHEMA = REPO / "command-center/schema/owner-question-closure.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0017-probe2 {msg}")
    return 1


def main() -> int:
    fix = S.build_fixtures()
    result = C.analyze_controls(REPO, fix)
    plants = C.proceeding_ids(result, "CTL-OPEN-1")
    print("planted_proceeding", sorted(plants))
    if "PLANT-0001" not in plants:
        return fail("PLANT-0001 missing from proceeding-on-default for CTL-OPEN-1")
    if C.control_verdicts(result).get("CTL-OPEN-1") != "UNANSWERED":
        return fail("CTL-OPEN-1 was not UNANSWERED")

    cov = result["coverage"]
    if not cov.get("exact_once"):
        return fail(f"control coverage not exact-once {cov}")
    packet_ids = result["packet_ids"]
    catalog_ids = result["catalog_ids"]
    expected = list(dict.fromkeys(catalog_ids + packet_ids))
    table_ids = [r["id"] for r in result["closure_table"]]
    if table_ids != expected:
        return fail(f"control table order/join {table_ids} != {expected}")

    if not ART.is_file():
        return fail("live artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)

    mutant = copy.deepcopy(doc)
    mutant.pop("closure_table", None)
    try:
        jsonschema.validate(mutant, schema)
    except jsonschema.ValidationError:
        mutant_red = True
    else:
        mutant_red = False
    print(f"schema_mutant_red={mutant_red}")
    if not mutant_red:
        return fail("schema accepted artifact without closure_table")

    live = C.analyze(REPO)
    live_cov = live["coverage"]
    print(
        "live_coverage catalog="
        + str(live_cov["catalog_count"])
        + " packet="
        + str(live_cov["packet_count"])
        + " table="
        + str(live_cov["table_count"])
        + " exact_once="
        + str(live_cov["exact_once"])
        + " brief_claimed_27_drift="
        + str(live_cov["count_drift_vs_brief_27"])
    )
    if not live_cov["exact_once"]:
        return fail(f"live join not exact-once missing={live_cov['missing']} dup={live_cov['duplicates']}")
    art_ids = [r["id"] for r in doc.get("closure_table") or []]
    if art_ids != live["ordered_ids"]:
        return fail("artifact closure_table does not match a fresh live join")
    if live_cov["catalog_count"] == 27:
        print("catalog_count_matches_brief_27=true")
    else:
        print(
            "catalog_count_matches_brief_27=false measured="
            + str(live_cov["catalog_count"])
            + " (zero appearances would be a join failure; extra live rows are count-drift)"
        )

    answered_controls = [
        r
        for r in result["closure_table"]
        if r["verdict"] == "ANSWERED"
    ]
    if len(answered_controls) < 5:
        return fail(f"need 5 ANSWERED controls, got {len(answered_controls)}")
    for row in answered_controls[:5]:
        quote = str(row.get("answer_quote") or "")
        if C.is_mere_ack(quote) or len(quote) < 8:
            return fail(f"reviewer: {row['id']} does not resolve ({quote!r})")
        print(f"reviewer_control {row['id']} resolves anchor={row['answer_anchor']}")

    live_marked = [
        r
        for r in live["closure_table"]
        if r.get("catalog_state") == "ANSWERED"
    ]
    if len(live_marked) < 5:
        return fail(f"need 5 catalog-marked ANSWERED rows to review, got {len(live_marked)}")
    for row in live_marked[:5]:
        if row["verdict"] == "ANSWERED":
            return fail(
                f"reviewer: catalog-marked {row['id']} classified ANSWERED without "
                "an owner utterance file:line on this tree"
            )
        if not row.get("reason"):
            return fail(f"reviewer: {row['id']} missing reason")
        print(
            f"reviewer_live {row['id']} verdict={row['verdict']} "
            f"grade={row.get('provenance_grade')} reason={row['reason']}"
        )

    proceeding = doc.get("proceeding_on_default") or []
    if not proceeding:
        return fail("live proceeding_on_default is empty")
    kinds = sorted({str(p.get("kind")) for p in proceeding})
    print("live_proceeding_count", len(proceeding), "kinds", kinds)
    print("SUCCESS:BLD-0017-probe2 plant-unit coverage reviewer-sample schema-mutant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
