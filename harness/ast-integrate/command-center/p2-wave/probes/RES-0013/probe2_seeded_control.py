#!/usr/bin/env python3
"""Named probe 2: seeded known-present control, clean silence, schema garbage."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extractor as E  # noqa: E402

ART = REPO / "command-center/research/RES-0013.json"
SCHEMA = REPO / "command-center/schema/research-registry.schema.json"
SENTINEL = (
    "SUCCESS:RES-0013 in the receipt AND a version-indexed breaking-change "
    "register where >=5 rows are corroborated by a second artifact"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0013-probe2 {msg}")
    return 1


def main() -> int:
    # Known-present FIRST — a detector that only reports live absence is inert.
    seed = E.extract_path(HERE / "fixtures" / "seeded-changelog.md", with_live_seconds=False)
    if not seed["seeded_found"]:
        return fail("seeded known-present not found")
    seed_ids = [r["id"] for r in seed["rows"]]
    if E.SEED_ID not in seed_ids:
        return fail(f"seed id absent ids={seed_ids}")

    clean = E.extract_path(HERE / "fixtures" / "clean-changelog.md", with_live_seconds=False)
    if clean["row_count"] != 0:
        return fail(f"clean fixture not silent count={clean['row_count']}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("catalog sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if int(doc.get("corroborated_count") or 0) < 5:
        return fail("corroborated_count < 5")
    if not (doc.get("seeded_control") or {}).get("known_present_run_first"):
        return fail("artifact did not record known-present-first")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    validator.validate(doc)
    rejected = 0
    for g in GARBAGE:
        if list(validator.iter_errors(g)):
            rejected += 1
    if rejected != 3:
        return fail(f"schema garbage rejected {rejected}/3")

    print(
        json.dumps(
            {
                "seeded_found": True,
                "seed_id": E.SEED_ID,
                "seed_ids": seed_ids,
                "clean_row_count": clean["row_count"],
                "garbage_rejected": rejected,
                "corroborated_count": doc.get("corroborated_count"),
                "known_present_run_first": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:RES-0013-probe2 seeded control fires; clean silent; schema discriminates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
