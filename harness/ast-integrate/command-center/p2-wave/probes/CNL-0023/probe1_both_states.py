#!/usr/bin/env python3
"""Probe 1: both-states vote-weight gate + negative control + non-vacuous schema.

FIRES on planted-bad (unjustified non-equal weight). SILENT on known-good.
Validation rejects before any council run. JSON Schema is a second, weaker
mechanism: it catches missing provenance, not a forged digest.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validator as V  # noqa: E402

UID = "CNL-0023"


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe1 {msg}")
    return 1


def main() -> int:
    good = V.load_fixture("known-good.json")
    bad = V.load_fixture("planted-bad.json")

    before = V.COUNCIL_RUNS
    vg = V.validate_spec(good)
    vb = V.validate_spec(bad)
    after_validate = V.COUNCIL_RUNS
    print(
        f"both-states good={vg['verdict']} unjustified={len(vg['unjustified'])} "
        f"bad={vb['verdict']} unjustified={len(vb['unjustified'])} "
        f"codes={vb['codes']}"
    )
    if vg["verdict"] != "ACCEPT" or vg["unjustified"]:
        return fail("known-good was not SILENT")
    if vb["verdict"] != "REJECT" or not vb["unjustified"]:
        return fail("planted-bad did not FIRE")
    want = {
        "seat.expert-unjustified": V.CODE_UNJUSTIFIED,
        "seat.expert-label": V.CODE_CLASS,
        "seat.tampered-digest": V.CODE_DIGEST,
    }
    got = {row["seat_id"]: row["code"] for row in vb["unjustified"]}
    if got != want:
        return fail(f"bad-seat codes {got} != {want}")
    if vg["council_ran"] or vb["council_ran"]:
        return fail("validate_spec started the council")
    if after_validate != before:
        return fail("validate_spec incremented COUNCIL_RUNS")

    run_bad = V.run_if_valid(bad)
    print(
        f"negative-control planted-bad seat.expert-unjustified vote_weight=2.5 "
        f"with no weight_provenance -> verdict={vb['verdict']} "
        f"code={got['seat.expert-unjustified']} council_ran={run_bad['council_ran']} "
        f"COUNCIL_RUNS={V.COUNCIL_RUNS}"
    )
    if run_bad["council_ran"] or V.COUNCIL_RUNS != before:
        return fail("council ran on planted-bad")

    sg = V.schema_errors(good)
    sb = V.schema_errors(bad)
    garbage = V.schema_errors({"totally": "unrelated", "passing_tests": 999999})
    print(f"schema good_errors={len(sg)} bad_errors={len(sb)} garbage_errors={len(garbage)}")
    if sg:
        return fail(f"schema not SILENT on known-good: {sg[:4]}")
    if not sb:
        return fail("schema vacuous: planted-bad produced 0 errors")
    if not any("weight_provenance" in e and "required" in e for e in sb):
        return fail("schema did not require weight_provenance on non-equal seat")
    if not garbage:
        return fail("schema accepted garbage; validator would be vacuous")
    # Honest split: forged digest is a valid JSON shape; schema stays silent.
    digest_only = {
        "id": "digest-only",
        "seats": [
            {
                "seat_id": "seat.tampered-digest",
                "vote_weight": 2.0,
                "weight_provenance": bad["seats"][5]["weight_provenance"],
            }
        ],
    }
    ds = V.schema_errors(digest_only)
    dv = V.validate_spec(digest_only)
    print(
        f"mechanism-split digest-mismatch schema_errors={len(ds)} "
        f"python_verdict={dv['verdict']} python_codes={dv['codes']}"
    )
    if ds:
        return fail("schema unexpectedly rejected well-shaped forged digest")
    if V.CODE_DIGEST not in dv["codes"]:
        return fail("python validator missed forged digest")

    art = (
        HERE.parents[3]
        / "command-center/design/council/CNL-0023-vote-rights-and-the-provenance-of-every-non-equal-weight.md"
    )
    if not art.is_file():
        return fail("design artifact missing")
    text = art.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0023" not in text:
        return fail("sentinel absent from artifact")
    json.loads(text)
    print("SUCCESS:CNL-0023-probe1 both-states unjustified-weight gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
