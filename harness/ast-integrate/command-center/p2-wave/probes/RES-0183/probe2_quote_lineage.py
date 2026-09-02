#!/usr/bin/env python3
"""Probe 2: independent quote lineage and coverage recount.

Re-parses owner_questions, re-reads each STATED quote at file:line,
schema-validates the artifact, and refuses a document that claims
OWNER-DECISIONS.md or 17-DECISION-LOG.md currently bind PR-ONLY.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import extract as E  # noqa: E402

ART = (
    REPO
    / "command-center/research/sources-frontier/"
    / "RES-0183-owner-decision-log-as-a-source-class.json"
)
SCHEMA = REPO / "command-center/schema/design-spec.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0183-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:RES-0183" not in text:
        return fail("sentinel absent")

    blob = E.build_constraints()
    oqs = E.answered_owner_questions()
    ids_json = sorted(r["id"] for r in oqs)
    if ids_json != blob["answered_oq_ids"]:
        return fail(f"OQ id recount {ids_json} != extract {blob['answered_oq_ids']}")
    oq3 = next(r for r in oqs if r["id"] == "OQ-3")
    if str(oq3.get("answer") or "").strip() != "PR-ONLY.":
        return fail("OQ-3 JSON answer is not PR-ONLY.")

    raw = (REPO / E.CATALOG_REL).read_text(encoding="utf-8")
    idx = raw.find('"id": "OQ-3"')
    if idx < 0:
        return fail("raw catalog missing OQ-3 id token")
    if '"answer": "PR-ONLY."' not in raw[idx : idx + 800]:
        return fail("raw OQ-3 window missing PR-ONLY answer")

    for c in blob["stated"]:
        if not E.verify_quote(c["path"], c["line"], c["quote"]):
            return fail(f"stated quote miss {c['id']} {c['anchor']}")
    for c in blob["inferred"]:
        if not c.get("owner_confirmation_required"):
            return fail(f"inferred {c['id']} not flagged for owner confirmation")
        if c.get("binding"):
            return fail(f"inferred {c['id']} marked binding")
        if not E.verify_quote(c["path"], c["line"], c["quote"]):
            return fail(f"inferred quote miss {c['id']}")

    art_ids = sorted(c["id"] for c in (doc.get("constraints") or {}).get("stated") or [])
    live_ids = sorted(c["id"] for c in blob["stated"])
    if art_ids != live_ids:
        return fail(f"artifact stated ids {art_ids} != live {live_ids}")

    honesty = doc.get("honesty") or {}
    if honesty.get("owner_decisions_records_pr_only") is True:
        return fail("artifact claims OWNER-DECISIONS.md records PR-ONLY")
    if honesty.get("decision_log_records_pr_only") is True:
        return fail("artifact claims 17-DECISION-LOG.md records PR-ONLY")
    if honesty.get("option_universe_present") is True:
        return fail("artifact claims 07-OPTION-UNIVERSE is present")
    if E.first_present(E.OPTION_UNIVERSE_CANDIDATES) is not None:
        return fail("option universe appeared on disk; recount the 70 ids")
    if "PR-ONLY" in (REPO / E.OWNER_REL).read_text(encoding="utf-8"):
        return fail("OWNER-DECISIONS.md now contains PR-ONLY; extract is stale")
    if "PR-ONLY" in (REPO / E.DECISION_LOG_REL).read_text(encoding="utf-8"):
        return fail("17-DECISION-LOG.md now contains PR-ONLY; extract is stale")

    distinct = str(doc.get("distinct_from_res_0127") or "")
    if "RES-0127" not in distinct:
        return fail("artifact does not distinguish RES-0127")
    if "two-tree" not in distinct.lower() and "two corpus trees" not in distinct.lower():
        return fail("RES-0127 distinction does not name the two-tree split")

    print(
        json.dumps(
            {
                "oq_json": ids_json,
                "stated_n": len(live_ids),
                "inferred_n": len(blob["inferred"]),
                "option_universe_present": False,
                "owner_pr_only": False,
                "log_pr_only": False,
            }
        )
    )
    print("SUCCESS:RES-0183-probe2 quote lineage + independent OQ recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
