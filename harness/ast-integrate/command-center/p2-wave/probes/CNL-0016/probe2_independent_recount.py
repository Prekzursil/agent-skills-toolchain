#!/usr/bin/env python3
"""Probe 2: independent recount + negative control recorded verbatim.

Reviewer path re-tabulates rosters from fixtures via recount.py (does not call
sampler.fisher_yates_take). Disagreement in the roster list blocks the unit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import recount as R  # noqa: E402
import sampler as S  # noqa: E402

NOTE = REPO / "command-center/design/council/CNL-0016-random-and-stratified-selection-with-replay-safe-seeding.md"
SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"
LOCAL_SCHEMA = HERE / "council-design-note.schema.json"


def _hex(seed_hex: str) -> bytes:
    return bytes.fromhex(seed_hex)


def main() -> int:
    people, spec = R.load_fixtures()
    seed_a = _hex(spec["seed_a_hex"])
    seed_b = _hex(spec["seed_b_hex"])

    disagreements = []
    rows = []
    for mode in ("uniform", "stratified"):
        author_a = S.run_draw(people, spec, seed_a, mode)
        author_b = S.run_draw(people, spec, seed_b, mode)
        if mode == "uniform":
            rev_a = R.recount_uniform(people, int(spec["uniform_k"]), seed_a)
            rev_b = R.recount_uniform(people, int(spec["uniform_k"]), seed_b)
        else:
            rev_a = R.recount_stratified(people, spec["stratified_quotas"], seed_a)
            rev_b = R.recount_stratified(people, spec["stratified_quotas"], seed_b)
        match_a = author_a["roster"] == rev_a["roster"]
        match_b = author_b["roster"] == rev_b["roster"]
        fp_match = author_a["frame_fingerprint"] == rev_a["frame_fingerprint"]
        if not (match_a and match_b and fp_match):
            disagreements.append(mode)
        rows.append(
            {
                "mode": mode,
                "author_seed_a": author_a["roster"],
                "reviewer_seed_a": rev_a["roster"],
                "author_seed_b": author_b["roster"],
                "reviewer_seed_b": rev_b["roster"],
                "match_a": match_a,
                "match_b": match_b,
                "frame_fingerprint": author_a["frame_fingerprint"],
            }
        )
        print(
            f"recount mode={mode} match_a={match_a} match_b={match_b} "
            f"fp_match={fp_match}"
        )
        print(f"  author_a={author_a['roster']}")
        print(f"  reviewer_a={rev_a['roster']}")

    if disagreements:
        print(f"FAILED:CNL-0016-probe2 reviewer disagreement modes={disagreements}")
        return 1

    # Negative control: frozen sampler (seed-ignoring) is the state this
    # check is meant to reject. Record verbatim.
    frame = S.eligible_frame(people)
    frozen_a = S.frozen_roster(frame, int(spec["uniform_k"]), seed_a)
    frozen_b = S.frozen_roster(frame, int(spec["uniform_k"]), seed_b)
    check_on_frozen = frozen_a == frozen_b
    check_on_live = rows[0]["author_seed_a"] == rows[0]["author_seed_b"]
    verbatim = (
        "NEGATIVE CONTROL CNL-0016: the different-seed check FIRES when a "
        f"frozen sampler returns the same roster under seed_a and seed_b "
        f"(frozen_a={frozen_a} frozen_b={frozen_b} fired={check_on_frozen}); "
        "the same check is SILENT on the live HMAC sampler "
        f"(live_a={rows[0]['author_seed_a']} live_b={rows[0]['author_seed_b']} "
        f"fired={check_on_live})."
    )
    print(verbatim)
    if not check_on_frozen:
        print("FAILED:CNL-0016-probe2 frozen sampler did not fire the check")
        return 1
    if check_on_live:
        print("FAILED:CNL-0016-probe2 live sampler looks frozen")
        return 1

    # Replay must refuse a drifted frame (drop P01).
    drifted = [p for p in people if p["id"] != "P01"]
    live_fp = S.run_draw(people, spec, seed_a, "uniform")["frame_fingerprint"]
    refused = False
    try:
        S.run_draw(drifted, spec, seed_a, "uniform", recorded_fp=live_fp)
    except ValueError as exc:
        refused = "fingerprint mismatch" in str(exc)
        print(f"frame_drift_refused={refused} err={exc}")
    if not refused:
        print("FAILED:CNL-0016-probe2 replay accepted a drifted frame")
        return 1

    if not NOTE.is_file() or not SCHEMA.is_file() or not LOCAL_SCHEMA.is_file():
        print("FAILED:CNL-0016-probe2 design note or schema missing")
        return 1
    note = json.loads(NOTE.read_text(encoding="utf-8"))
    # Catalog output_schema is a $ref shim to ast-integrate.invalid; jsonschema
    # 4.10.3 RefResolver tries the network. Validate against the per-unit schema.
    schema = json.loads(LOCAL_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(note)
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    garbage_rejected = False
    try:
        jsonschema.Draft7Validator(schema).validate(garbage)
    except jsonschema.ValidationError:
        garbage_rejected = True
    if not garbage_rejected:
        print("FAILED:CNL-0016-probe2 schema is vacuous")
        return 1
    recorded = (note.get("mechanism") or {}).get("recorded_rosters") or {}
    want_u = rows[0]["reviewer_seed_a"]
    want_s = rows[1]["reviewer_seed_a"]
    if recorded.get("uniform_seed_a") != want_u or recorded.get("stratified_seed_a") != want_s:
        print(
            "FAILED:CNL-0016-probe2 design-note roster != reviewer recount "
            f"note_u={recorded.get('uniform_seed_a')} live_u={want_u}"
        )
        return 1
    if "SUCCESS:CNL-0016" not in json.dumps(note):
        print("FAILED:CNL-0016-probe2 sentinel missing from design note")
        return 1
    print("schema_ok=True garbage_rejected=True note_roster_matches_recount=True")
    print("SUCCESS:CNL-0016-probe2 independent recount and negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
