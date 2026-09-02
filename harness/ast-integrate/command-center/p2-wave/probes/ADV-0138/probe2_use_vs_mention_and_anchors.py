#!/usr/bin/env python3
"""Probe 2: use-vs-mention both-states, schema, live OWNER-STATED anchors.

Mechanically independent of probe 1: re-resolves every OWNER-STATED and
OWNER-IMPLIED-BY-INFERENCE quote against the file at the cited line, and
runs the deferred-mention control that keyword matching fails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0138-authority-provenance.json"
SCHEMA = REPO / "command-center/schema/decision-provenance.schema.json"
SENTINEL = (
    "SUCCESS:ADV-0138 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every binding decision "
    "carries a classification and, where OWNER-STATED, a verbatim quote with "
    "a resolvable file:line; the two known-present decisions classified "
    "correctly and the planted laundering was caught. Any other terminal "
    "state is FAILED:ADV-0138 <classification> with the diagnostic tail attached."
)
GARBAGE = [
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"x": "x" * 2000},
]


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0138-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:ADV-0138-probe2 full sentinel absent")
        return 1
    doc = json.loads(text)
    if doc.get("unit_id") != "ADV-0138":
        print("FAILED:ADV-0138-probe2 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:ADV-0138-probe2 self-declared", doc.get("state"))
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print("FAILED:ADV-0138-probe2 schema", errors[0].message)
        return 1
    rejected = sum(1 for g in GARBAGE if not validator.is_valid(g))
    if rejected != 3:
        print("FAILED:ADV-0138-probe2 schema vacuous", rejected)
        return 1

    uvm = C.use_vs_mention_bundle()
    if not uvm["pass"]:
        print("FAILED:ADV-0138-probe2 use-vs-mention")
        print(json.dumps(uvm, default=str)[:2000])
        return 1
    if uvm["semantic"]["classification"] != C.PROGRAM:
        print("FAILED:ADV-0138-probe2 semantic not PROGRAM-AUTHORED")
        return 1
    if uvm["naive_keyword"]["classification"] != C.OWNER_STATED:
        print("FAILED:ADV-0138-probe2 naive did not take the keyword bait")
        return 1
    if not uvm["both_states_discriminates"]:
        print("FAILED:ADV-0138-probe2 both-states silent")
        return 1
    stored = (doc.get("controls") or {}).get("use_vs_mention") or {}
    if stored.get("semantic_classification") != C.PROGRAM:
        print("FAILED:ADV-0138-probe2 artifact semantic drift")
        return 1
    if stored.get("naive_keyword_classification") != C.OWNER_STATED:
        print("FAILED:ADV-0138-probe2 artifact naive drift")
        return 1

    live = doc.get("binding_decisions") or []
    if len(live) < 5:
        print("FAILED:ADV-0138-probe2 too few live rows")
        return 1
    checked = []
    for row in live:
        cls = row.get("classification")
        if not cls:
            print("FAILED:ADV-0138-probe2 missing classification", row.get("id"))
            return 1
        if cls in {C.OWNER_STATED, C.IMPLIED}:
            quote = row.get("owner_quote") or ""
            anchor = row.get("anchor") or ""
            ok, why = C.resolve_anchor(anchor, quote)
            if not ok:
                print(
                    "FAILED:ADV-0138-probe2 live anchor",
                    row.get("id"),
                    why,
                )
                return 1
            if cls == C.IMPLIED and len(row.get("inference_step") or "") < 20:
                print("FAILED:ADV-0138-probe2 implied missing step", row.get("id"))
                return 1
            checked.append({"id": row.get("id"), "anchor": why, "cls": cls})

    if not any(r.get("id") == "BD-RELEASE-PR-ONLY" for r in live):
        print("FAILED:ADV-0138-probe2 live PR-ONLY row absent")
        return 1
    live_pr = next(r for r in live if r["id"] == "BD-RELEASE-PR-ONLY")
    if live_pr["classification"] != C.OWNER_STATED:
        print("FAILED:ADV-0138-probe2 live PR-ONLY not OWNER-STATED")
        return 1

    payload = {
        "pass": True,
        "probe": "probe2-use-vs-mention-and-anchors",
        "unit_id": "ADV-0138",
        "schema_ok": True,
        "garbage_rejected": rejected,
        "use_vs_mention_semantic": uvm["semantic"]["classification"],
        "use_vs_mention_naive": uvm["naive_keyword"]["classification"],
        "both_states_discriminates": True,
        "live_anchors_checked": checked,
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "use_vs_mention semantic=PROGRAM-AUTHORED naive=OWNER-STATED "
        f"anchors={len(checked)} schema_ok=True"
    )
    print("SUCCESS:ADV-0138-probe2 use-vs-mention anchors reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
