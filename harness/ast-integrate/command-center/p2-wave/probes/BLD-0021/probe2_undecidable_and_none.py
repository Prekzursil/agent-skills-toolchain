#!/usr/bin/env python3
"""Probe 2: 58 UNDECIDABLE must reproduce; planted absent is RESOLVES-NONE.

Also: ten UNDECIDABLE contexts carry no discriminating token (reviewer
control). Guessing is forbidden — a drop in the 58 without a per-item
explanation fails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import resolver as R  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0021.json"
SCHEMA = REPO / "command-center/schema/reference-resolution.schema.json"
KNOWN = S.docs_161819()


def main() -> int:
    S.ensure_fixtures()
    decls = R.load_registries(S.registry_paths())
    refs = R.sweep_files(S.corpus_files(), decls, detect_mentions=True)
    known = [
        r
        for r in refs
        if r.path in KNOWN and r.classification == "UNDECIDABLE"
    ]
    none = [r for r in refs if r.token == S.PLANTED_ABSENT]
    many = [r for r in refs if r.classification == "RESOLVES-MANY"]
    print(
        json.dumps(
            {
                "undecidable_in_docs_16_18_19": len(known),
                "planted_absent": [R.as_dict(r) for r in none],
                "resolves_many": len(many),
            },
            sort_keys=True,
        )[:4000]
    )
    if len(known) != 58:
        print(
            f"FAILED:BLD-0021-probe2 expected 58 UNDECIDABLE, got {len(known)}"
        )
        return 1
    if not none or none[0].classification != "RESOLVES-NONE":
        print("FAILED:BLD-0021-probe2 planted ZX-9999 is not RESOLVES-NONE")
        return 1
    if not many:
        print("FAILED:BLD-0021-probe2 expected a RESOLVES-MANY control (RRR-1)")
        return 1

    sample = known[:10]
    for r in sample:
        if r.discriminators_in_context:
            print(
                f"FAILED:BLD-0021-probe2 UNDECIDABLE has discriminator "
                f"{r.path}:{r.line} {r.discriminators_in_context}"
            )
            return 1
        if len(r.candidates) < 2:
            print(
                f"FAILED:BLD-0021-probe2 UNDECIDABLE without two meanings "
                f"{r.path}:{r.line}"
            )
            return 1

    if not ART.is_file():
        print("FAILED:BLD-0021-probe2 receipt missing")
        return 1
    raw = ART.read_text(encoding="utf-8")
    doc = json.loads(raw)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:BLD-0021-probe2 self-declared {doc.get('state')}")
        return 1
    if doc.get("undecidable_in_docs_16_18_19") != 58:
        print("FAILED:BLD-0021-probe2 artifact count is not 58")
        return 1
    if doc.get("planted_absent_verdict") != "RESOLVES-NONE":
        print("FAILED:BLD-0021-probe2 artifact planted_absent_verdict")
        return 1
    if "SUCCESS:BLD-0021" not in raw:
        print("FAILED:BLD-0021-probe2 sentinel absent")
        return 1

    art_und = [
        row
        for row in doc.get("references") or []
        if row.get("path") in KNOWN and row.get("classification") == "UNDECIDABLE"
    ]
    if len(art_und) != 58:
        print(f"FAILED:BLD-0021-probe2 artifact UNDECIDABLE rows {len(art_und)}")
        return 1
    guessed = [
        row
        for row in doc.get("undecidable_owner_escalation") or []
        if row.get("guessed") is not False or row.get("status") != "DEFERRED"
    ]
    if guessed:
        print("FAILED:BLD-0021-probe2 owner packet guessed or not DEFERRED")
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    try:
        jsonschema.validate(garbage, schema)
    except jsonschema.ValidationError:
        pass
    else:
        print("FAILED:BLD-0021-probe2 schema accepted garbage")
        return 1

    ten = doc.get("reviewer", {}).get("ten_undecidable_sample") or []
    if len(ten) != 10:
        print("FAILED:BLD-0021-probe2 reviewer sample is not 10")
        return 1
    for row in ten:
        if row.get("discriminators_in_context"):
            print("FAILED:BLD-0021-probe2 reviewer sample has a discriminator")
            return 1

    print("SUCCESS:BLD-0021-probe2 undecidable-58 and planted-none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
