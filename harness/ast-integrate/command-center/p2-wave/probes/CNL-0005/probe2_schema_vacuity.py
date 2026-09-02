#!/usr/bin/env python3
"""Probe 2: Draft 2020-12 validator over every record + vacuity control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import participant as P  # noqa: E402
import schema_check as S  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md"
)
NOTE_SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"
SENTINEL = "SUCCESS:CNL-0005"


def fail(msg: str, extra: object | None = None) -> int:
    print(f"FAILED:CNL-0005-probe2 {msg}")
    if extra is not None:
        text = extra if isinstance(extra, str) else json.dumps(extra, indent=2, default=str)
        print(text[:4000])
    return 1


def main() -> int:
    self_errs = S.check_schema_self()
    if self_errs:
        return fail("participant.schema.json is not a valid 2020-12 schema", self_errs)
    print("participant.schema.json Draft202012Validator.check_schema ok")

    good_records = P.good_roster() + [P.distinct_model_pair()[0], P.distinct_model_pair()[1]]
    total_errors = 0
    per_record = []
    for rec in good_records:
        n = S.error_count(rec)
        per_record.append({"seat_id": rec.get("seat_id"), "errors": n})
        total_errors += n
    print(f"good_records={len(good_records)} total_error_count={total_errors}")
    print(json.dumps(per_record, sort_keys=True))
    if total_errors != 0:
        return fail("expected 0 schema errors on good records", per_record)

    roster = {"id": "cnl-0005-good", "seats": P.good_roster()}
    roster_errs = S.error_count(roster, "roster")
    print(f"good_roster_schema_errors={roster_errs}")
    if roster_errs != 0:
        return fail("good roster must have 0 schema errors", S.errors_of(roster, "roster"))

    planted = P.invalid_missing_model()
    planted_errs = S.errors_of(planted)
    planted_n = len(planted_errs)
    print(f"planted_missing_model error_count={planted_n} errors={planted_errs[:6]}")
    if planted_n <= 0:
        return fail("validator accepted the missing-model record; vacuous")

    extra = P.invalid_extra_field()
    extra_errs = S.errors_of(extra)
    print(f"planted_extra_field error_count={len(extra_errs)} errors={extra_errs[:6]}")
    if not extra_errs:
        return fail("additionalProperties is not live")

    neg_w = P.invalid_negative_weight()
    neg_errs = S.errors_of(neg_w)
    print(f"planted_negative_weight error_count={len(neg_errs)} errors={neg_errs[:6]}")
    if not neg_errs:
        return fail("exclusiveMinimum on vote_weight is not live")

    garbage_n = []
    for g in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"seat_id": "x" * 2000},
    ):
        n = S.error_count(g)
        garbage_n.append(n)
        if n <= 0:
            return fail("schema accepted garbage", g)
    print(f"garbage_error_counts={garbage_n}")

    verbatim = (
        "On the rejected state (participant missing required property 'model') "
        f"Draft202012Validator reports error_count={planted_n} messages={planted_errs}. "
        "On the accepted state (three-seat good roster) the same validator "
        f"reports error_count=0 over {len(good_records)} records plus the roster envelope."
    )
    print(f"negative_control_verbatim={verbatim}")

    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    note_schema = json.loads(NOTE_SCHEMA.read_text(encoding="utf-8"))
    note_errs = [
        e.message for e in jsonschema.Draft7Validator(note_schema).iter_errors(doc)
    ]
    print(f"design_note_schema_errors={len(note_errs)}")
    if note_errs:
        return fail("design note failed council-design-note.schema.json", note_errs)

    recorded = doc.get("schema_validation") or {}
    if recorded.get("good_record_error_count") != 0:
        return fail("artifact good_record_error_count is not 0")
    if int(recorded.get("planted_invalid_error_count") or 0) <= 0:
        return fail("artifact planted_invalid_error_count is not >0")

    # Independent recount vs artifact (reviewer role).
    if recorded.get("planted_invalid_error_count") != planted_n:
        return fail(
            "reviewer recount disagrees with artifact planted_invalid_error_count",
            {"artifact": recorded.get("planted_invalid_error_count"), "live": planted_n},
        )

    print(
        json.dumps(
            {
                "good_record_error_count": 0,
                "planted_invalid_error_count": planted_n,
                "additionalProperties_live": True,
                "exclusiveMinimum_live": True,
                "garbage_rejected": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNL-0005-probe2 jsonschema Draft202012Validator vacuity control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
