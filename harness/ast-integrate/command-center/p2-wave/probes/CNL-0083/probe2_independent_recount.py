#!/usr/bin/env python3
"""Probe 2: independent recount from visit ledgers + A10 parse.

Does not trust evaluate.reason strings. Re-tabulates coverage and squares
from fixtures/fire and fixtures/silent-search, then checks the design
artifact recorded the same numbers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import a10_grammar as G  # noqa: E402
from record import independent_recount  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0083-executable-stopping-example-proof-of-impossibility-true.schema.json"
)
RHS = 7


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ok, why = G.accepts_unchanged(G.UNIT_EXPRESSION)
    print(f"parse_unchanged={ok} why={why}")
    if not ok:
        print("FAILED:CNL-0083-probe2 A10 parse")
        return 1
    for row in G.parse_all_spec_examples():
        print(f"A10 line={row['line']} accepted={row['accepted']} expr={row['expression']}")
        if not row["accepted"]:
            print("FAILED:CNL-0083-probe2 spec example rejected")
            return 1

    fire_rec = load(HERE / "fixtures/fire/record.json")
    fire_vis = load(HERE / "fixtures/fire/visits.json")["visits"]
    silent_rec = load(HERE / "fixtures/silent-search/record.json")
    silent_vis = load(HERE / "fixtures/silent-search/visits.json")["visits"]

    fire_members = fire_rec["search_space"]["members"]
    silent_members = silent_rec["search_space"]["members"]
    fire_tab = independent_recount(fire_members, fire_vis, RHS)
    silent_tab = independent_recount(silent_members, silent_vis, RHS)

    print(json.dumps({"fire_recount": fire_tab, "silent_recount": silent_tab}, indent=2, sort_keys=True))

    if fire_tab["coverage"] != 4 or fire_tab["cardinality"] != 4:
        print("FAILED:CNL-0083-probe2 fire coverage recount")
        return 1
    if fire_tab["squares"] != {0: 0, 1: 1, 2: 4, 3: 9}:
        print("FAILED:CNL-0083-probe2 fire squares recount")
        return 1
    if fire_tab["hits"]:
        print("FAILED:CNL-0083-probe2 fire unexpectedly has a square==7")
        return 1
    if not fire_tab["proof"]:
        print("FAILED:CNL-0083-probe2 fire recount did not qualify as proof")
        return 1

    if silent_tab["coverage"] != 2 or silent_tab["cardinality"] != 4:
        print("FAILED:CNL-0083-probe2 silent coverage recount")
        return 1
    if silent_tab["complete"]:
        print("FAILED:CNL-0083-probe2 silent search marked complete")
        return 1
    if silent_tab["proof"]:
        print("FAILED:CNL-0083-probe2 unsuccessful search counted as proof")
        return 1
    if fire_tab["proof"] == silent_tab["proof"]:
        print("FAILED:CNL-0083-probe2 recount silent in both states")
        return 1

    if not ART.is_file():
        print("FAILED:CNL-0083-probe2 design artifact missing")
        return 1
    art = load(ART)
    if "SUCCESS:CNL-0083" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNL-0083-probe2 sentinel absent")
        return 1
    if art.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0083-probe2 self-declared {art.get('state')}")
        return 1
    review = art.get("independent_recount") or {}
    if int(review.get("fire_coverage") or -1) != fire_tab["coverage"]:
        print("FAILED:CNL-0083-probe2 artifact fire_coverage disagrees with recount")
        return 1
    if int(review.get("silent_coverage") or -1) != silent_tab["coverage"]:
        print("FAILED:CNL-0083-probe2 artifact silent_coverage disagrees with recount")
        return 1
    if review.get("fire_proof") is not True or review.get("silent_proof") is not False:
        print("FAILED:CNL-0083-probe2 artifact proof flags disagree with recount")
        return 1
    if art.get("expression") != G.UNIT_EXPRESSION:
        print("FAILED:CNL-0083-probe2 expression not verbatim")
        return 1

    schema = art.get("proof_record_schema")
    if not isinstance(schema, dict) or schema.get("type") != "object":
        print("FAILED:CNL-0083-probe2 proof_record_schema missing")
        return 1
    try:
        import jsonschema

        jsonschema.Draft7Validator(schema).validate(fire_rec)
        print("schema_validates_fire_record=True")
        try:
            jsonschema.Draft7Validator(schema).validate(
                load(HERE / "fixtures/silent-unfalsifiable/record.json")
            )
            print("FAILED:CNL-0083-probe2 schema accepted unfalsifiable record")
            return 1
        except jsonschema.ValidationError:
            print("schema_rejects_unfalsifiable=True")
    except ImportError:
        print("jsonschema_unavailable_skip_draft7")

    print(
        "SUCCESS:CNL-0083-probe2 independent recount "
        f"fire_proof={fire_tab['proof']} silent_proof={silent_tab['proof']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
