#!/usr/bin/env python3
"""Both-states + extraction-control for the singularity detector."""
from __future__ import annotations

import json
from pathlib import Path

import parser as P

HERE = Path(__file__).resolve().parent
SINGULAR = HERE / "fixtures" / "singular.json"
DUPLICATE = HERE / "fixtures" / "duplicate.json"
HYBRID = HERE / "fixtures" / "hybrid-singular.json"
KNOWN_SKILL_PATH = "command-center/control-plane/A1/capabilities/skills/*.skill.json"
KNOWN_SKILL_ID = "skill.council"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def both_states() -> dict:
    singular = P.evaluate(load(SINGULAR))
    duplicate = P.evaluate(load(DUPLICATE))
    hybrid = P.evaluate(load(HYBRID))

    known = P.find_row(
        singular["rows"],
        capability_id=KNOWN_SKILL_ID,
        path_contains="capabilities/skills",
    )
    dup_skill = P.find_row(duplicate["rows"], capability_id=KNOWN_SKILL_ID)
    dup_auths = sorted({(r["authority"], r["path"]) for r in dup_skill})

    # Extraction control: refuse a zero-duplicate PASS if the known row is missing.
    extraction_found = len(known) >= 1
    singular_pass = bool(singular["singular"]) and extraction_found and not singular["zero_rows"]
    # Refuse a FAIL that did not actually extract two authorities.
    duplicate_fail = (not duplicate["singular"]) and len(dup_auths) >= 2

    # Prose "singular": true on the duplicate fixture must not hide the set-op fail.
    prose_did_not_pass = duplicate.get("prose_singular_field") is True and not duplicate["singular"]

    return {
        "singular_ok": singular_pass,
        "singular_row_count": len(singular["rows"]),
        "singular_duplicates": singular["duplicates"],
        "duplicate_fails": duplicate_fail,
        "duplicate_authority_count": len(dup_auths),
        "duplicate_authorities": [
            {"authority": a, "path": p} for a, p in dup_auths
        ],
        "duplicate_prose_ignored": prose_did_not_pass,
        "hybrid_fixture_singular": bool(hybrid["singular"]) and not hybrid["zero_rows"],
        "hybrid_row_count": len(hybrid["rows"]),
        "extraction_found_known_row": extraction_found,
        "known_row": known[0] if known else None,
        "pass": (
            singular_pass
            and duplicate_fail
            and prose_did_not_pass
            and extraction_found
            and bool(hybrid["singular"])
            and not hybrid["zero_rows"]
        ),
    }
