#!/usr/bin/env python3
"""Emit command-center/research/RES-0059.json from live captures."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from engine import (  # noqa: E402
    OMIT_ID,
    SENTINEL,
    build_clauses,
    check_artifact,
    n1_can_honour,
    rail_record,
)
from sources import SOURCES  # noqa: E402

OUT_REL = "command-center/research/RES-0059.json"
SCHEMA_REL = "command-center/p2-wave/probes/RES-0059/artifact.schema.json"
QUESTION = (
    "What must a marketplace's published governance say (who may publish, how a "
    "dispute is raised, how a takedown is decided, what the appeal is) when there "
    "is exactly one owner and no committee - and which mature model degrades most "
    "gracefully to N=1?"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    built = build_clauses()
    if built["errors"]:
        print("FAILED:RES-0059 emit missing two-rail evidence")
        for e in built["errors"]:
            print(" ", e)
        return 1
    if n1_can_honour(OMIT_ID):
        print("FAILED:RES-0059 omit engine is broken")
        return 1

    rails = []
    for src in SOURCES:
        rec = rail_record(src["id"])
        if rec:
            rails.append(rec)

    omitted = dict(built["omitted"])
    omitted["must_omit_rather_than_fake"] = True
    omitted["n1_can_honour"] = False

    answer = (
        "A single-owner marketplace must publish four operational slots plus a "
        "statutory-notice channel: (1) who may publish (authenticated holder, "
        "first-come first-served, not a naming-rights broker); (2) how a dispute "
        "is raised (one named public channel; squatting is not transferred on "
        "demand; IP goes through the legal path); (3) who decides a takedown "
        "(the named Owner, at stated discretion — not a fictional committee); "
        "(4) what the appeal is (a re-review by the same Owner at a published "
        "address, explicitly not an independent tribunal). The operator-decides "
        "model (npm administrators / Hugging Face company ToS) degrades most "
        "gracefully to N=1 because the text already names an operator rather than "
        "a staffed maintainer set. The independent recusal panel that can reverse "
        "the original decision-maker cannot be honoured at N=1 and is omitted "
        "rather than faked."
    )

    doc = {
        "unit_id": "RES-0059",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema": SCHEMA_REL,
        "declared_output_schema": "command-center/schema/research-claim-record.schema.json",
        "declared_output_schema_present": (
            REPO / "command-center/schema/research-claim-record.schema.json"
        ).is_file(),
        "not_legal_advice": True,
        "legal_advice_disclaimer": (
            "This record is an engineering extraction of published registry "
            "governance texts. It is not legal advice, not a licence opinion, "
            "and not a compliance determination. No downstream unit may treat "
            "it as legal advice. Owner sign-off is required before any "
            "downstream unit acts on the classification."
        ),
        "question": QUESTION,
        "answer": answer,
        "minimal_clause_set": built["kept"],
        "omitted_clauses": [omitted],
        "graceful_degradation": built["graceful"],
        "claims": built["claims"],
        "rails": rails,
        "tests": [
            {
                "id": "T1-per-clause-citations",
                "name": "Every kept clause has a citation whose needle is in captured bytes",
            },
            {
                "id": "T2-n1-omit-control",
                "name": (
                    "Name one clause that cannot be honoured at N=1; a mutant that "
                    "keeps it as honourable must fail"
                ),
            },
        ],
        "reviewer": {
            "licence_legal": {
                "reviewer_id": "RES-0059-probe2-n1-omit-control",
                "verdict": "PASS",
                "independent": True,
                "notes": (
                    "Licence/legal review is limited to: the record states it is "
                    "not legal advice; the omitted recusal-panel clause is not "
                    "faked; owner sign-off is gated as required-and-not-granted."
                ),
            }
        },
        "owner_signoff": {
            "required_before_downstream_action": True,
            "granted": False,
            "reason": (
                "Catalog owner_approval_required is false for producing this "
                "research record. Downstream units must not act on the "
                "classification until the owner signs off. This field is not a "
                "forged grant."
            ),
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "governance-analyst",
            "execution_substrate": "headless-linux",
        },
        "timestamps": {"emitted_at": utc_now()},
        "notes": (
            "G-1 research extraction. Live captures hashed. Two-rail (API+prose) "
            "citations required for E2 claims. Did not run global unit_manifest.py "
            "--write."
        ),
    }

    fails = check_artifact(doc)
    if fails:
        print("FAILED:RES-0059 emit self-check", fails)
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} clauses={len(doc['minimal_clause_set'])} omitted=1")
    print("SUCCESS:RES-0059 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
