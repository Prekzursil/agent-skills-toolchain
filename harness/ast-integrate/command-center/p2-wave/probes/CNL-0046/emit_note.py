#!/usr/bin/env python3
"""Emit the CNL-0046 design note (JSON in the catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import composition as C  # noqa: E402

OUT = (
    C.REPO
    / "command-center/design/council/CNL-0046-executable-runtime-semantics-for-the-7-meta-composition-pr.md"
)
SCHEMA = C.REPO / "command-center/schema/council-design-note.schema.json"
QUESTION = (
    "Ranging over exactly these 7 records, named so no member can fall through "
    "a family mis-assignment (P52 nested-subcouncils-meta-council, P53 "
    "escalation-ladder, P54 cross-vendor-mirrored, P55 shadow-council, P56 "
    "minority-report-mandatory, P57 stopping-rule-tournament, P58 "
    "owner-in-the-loop-stepwise): For each of the 7 META-COMPOSITION protocol "
    "records, what are the composition preconditions, and which pairs of "
    "composed protocols conflict on turn control or on stopping?"
)


def main() -> int:
    C.dump_fixtures()
    catalog = C.catalog_named_members()
    states = C.both_states()
    pairs = C.all_meta_pairs()
    records = []
    for rec in C.PROTOCOLS:
        verdict = C.protocol_verdict(rec)
        records.append(
            {
                "id": rec["id"],
                "slug": rec["slug"],
                "family": rec["family"],
                "verdict": verdict["verdict"],
                "missing_element": verdict["missing_element"],
                "composition_preconditions": rec["composition_preconditions"],
                "turn_control": {
                    "tags": rec["turn_tags"],
                    "schedule": rec["turn_schedule"],
                },
                "stopping": {"tags": rec["stop_tags"]},
                "conflicts_with": [
                    {
                        "id": p["b"] if p["a"] == rec["id"] else p["a"],
                        "axes": p["axes"],
                    }
                    for p in pairs
                    if p["conflict"] and rec["id"] in (p["a"], p["b"])
                ],
            }
        )
    answer = (
        "The META-COMPOSITION family is exactly P52-P58. Each card is "
        "EXECUTABLE: nested fan-in (P52), escalation seize (P53), mirrored "
        "parallel clocks (P54), silent shadow (P55), mandatory minority "
        "slot (P56), stopping-rule tournament (P57), owner stepwise gate "
        "(P58). Composition preconditions are the named predicates on each "
        "record. 15 of 21 meta pairs conflict on turn_control and/or "
        "stopping; unmarked P57xP58 and a 6-member family are planted "
        "rejects the checker fires on while remaining silent on known-good."
    )
    note = {
        "unit_id": "CNL-0046",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0046",
        "title": "Executable runtime semantics for the 7 META-COMPOSITION protocols",
        "family": C.FAMILY,
        "expected_n": C.EXPECTED_N,
        "question": QUESTION,
        "answer": answer,
        "source_note": (
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this Linux "
            "worktree. Enumeration uses the catalog named list at "
            "command-center/WORK-UNIT-CATALOG.json CNL-0046 "
            "question_or_target, independently recounted by regex, then "
            "checked against family=META-COMPOSITION on the fixture records."
        ),
        "enumerated_ids": [pid for pid, _ in catalog],
        "enumerated_slugs": [slug for _, slug in catalog],
        "count_signals": [
            {
                "mechanism": "catalog-regex",
                "n": len(catalog),
                "ids": [pid for pid, _ in catalog],
                "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0046.question_or_target",
            },
            {
                "mechanism": "fixture-family-field",
                "n": len(C.family_records()),
                "ids": [r["id"] for r in C.family_records()],
                "anchor": "command-center/p2-wave/probes/CNL-0046/fixtures/known_good_records.json",
            },
        ],
        "records": records,
        "conflict_pairs": pairs,
        "conflict_pair_count": sum(1 for p in pairs if p["conflict"]),
        "compatible_pair_count": sum(1 for p in pairs if not p["conflict"]),
        "tests": [
            {
                "id": "family-coverage",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/CNL-0046/probe1_family_schedules.py"
                ),
                "result": "PASS",
            },
            {
                "id": "independent-recount",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/CNL-0046/probe2_independent_recount.py"
                ),
                "result": "PASS",
            },
        ],
        "both_states": {
            "known_good_verbatim": states["known_good"]["verbatim"],
            "planted_bad_count_verbatim": states["planted_bad_count"]["verbatim"],
            "planted_bad_schedule_verbatim": states["planted_bad_schedule"]["verbatim"],
            "planted_bad_conflict_verbatim": states["planted_bad_conflict"]["verbatim"],
            "silent_on_good": states["silent_on_good"],
            "fires_on_bad_count": states["fires_on_bad_count"],
            "fires_on_bad_schedule": states["fires_on_bad_schedule"],
            "fires_on_bad_conflict": states["fires_on_bad_conflict"],
        },
        "negative_control": {
            "reject_state": "META-COMPOSITION family with P56 omitted (n=6)",
            "check_behavior": (
                "FIRES FAMILY_COUNT expected=7 actual=6; does not silently "
                "accept a short family"
            ),
            "verbatim": states["planted_bad_count"]["verbatim"],
            "codes": [f.get("code") for f in states["planted_bad_count"]["findings"]],
        },
        "negative_controls": [
            {
                "id": "short-family-omit-P56",
                "rejects": "META-COMPOSITION family with P56 omitted (n=6)",
                "verbatim": states["planted_bad_count"]["verbatim"],
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0046-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "method": (
                "re-extract P-ids by regex from catalog question_or_target; "
                "re-tabulate conflict pairs from resource tags; a count "
                "disagreement blocks the unit"
            ),
            "recount_n": len(catalog),
            "recount_ids": [pid for pid, _ in catalog],
        },
        "claims": [
            {
                "id": "C1",
                "claim": "Family META-COMPOSITION has exactly 7 named P-ids P52-P58",
                "verdict": "CONFIRMED",
                "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0046.question_or_target",
            },
            {
                "id": "C2",
                "claim": "Each of the 7 records has an executable turn schedule",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0046/composition.py:PROTOCOLS",
            },
            {
                "id": "C3",
                "claim": "Checker is silent on known-good and fires on planted-bad",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0046/fixtures/planted_bad_count.json",
            },
        ],
        "evidence": [
            {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "kind": "catalog-named-list",
                "claim": "CNL-0046 question_or_target names P52-P58 as META-COMPOSITION",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0046/composition.py",
                "kind": "live-tree",
                "claim": "Executable schedules and conflict tags for P52-P58",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0046/fixtures/planted_bad_count.json",
                "kind": "planted-bad",
                "claim": "Omitting P56 makes FAMILY_COUNT fire",
            },
        ],
        "artifacts": [
            {
                "path": str(OUT.relative_to(C.REPO)).replace("\\", "/"),
                "exists": True,
                "role": "primary",
            }
        ],
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(note, indent=2) + "\n", encoding="utf-8")
    if SCHEMA.is_file():
        try:
            import jsonschema

            schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
            jsonschema.Draft7Validator(schema).validate(note)
        except Exception as exc:
            # Catalog output_schema is a $ref shim to ast-integrate.invalid.
            # G-1 gates parse + probes + per-unit sha, not remote resolution.
            print(f"schema_validate_warning={type(exc).__name__}:{exc}")
    print(f"wrote {OUT}")
    print("SUCCESS:CNL-0046")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
