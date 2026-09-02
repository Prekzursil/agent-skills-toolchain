#!/usr/bin/env python3
"""Probe 2: rewrite three real error messages into the A8 contract.

Before: live shipped strings must fail the contract.
After: DESIGN.json rewrites must pass.
Needles must still be present in the cited source files.
Negative control: strip next_action from a rewrite — checker must fire.
Both-states: a well-formed after stays silent.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import design_io as D  # noqa: E402
import error_contract as E  # noqa: E402
import real_errors as R  # noqa: E402
import surface as S  # noqa: E402

DESIGN = REPO / "command-center/phase3/A8/DESIGN.json"
SAMPLES = HERE / "samples.json"


def main() -> int:
    live = R.locate_all(REPO)
    if len(live) != 3:
        print(f"FAILED:ARC-0052-probe2 expected 3 live errors, got {len(live)}")
        return 1
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    rewrites = {row["id"]: row for row in D.error_rewrites(design)}
    fail = False
    for spec in live:
        before_ok, before_why = E.check_text(spec["before"])
        after_fields = spec["after"]
        recorded = rewrites.get(spec["id"]) or {}
        rec_after = recorded.get("after") or {}
        after_ok, after_why = E.check_fields(after_fields)
        rec_ok, rec_why = E.check_fields(rec_after) if rec_after else (False, "absent")
        match = rec_after == after_fields
        print(
            f"error id={spec['id']} anchor={spec['anchor']} "
            f"before_fail={not before_ok} ({before_why}) "
            f"after_pass={after_ok} ({after_why}) recorded={rec_ok} match={match}"
        )
        if before_ok or not after_ok or not rec_ok or not match:
            fail = True
        formatted = E.format_message(after_fields)
        fmt_ok, fmt_why = E.check_text(formatted)
        if not fmt_ok:
            print(f"FAILED:ARC-0052-probe2 formatted after failed {fmt_why}")
            fail = True

    stripped = copy.deepcopy(live[0]["after"])
    stripped.pop("next_action")
    stripped_ok, stripped_why = E.check_fields(stripped)
    good_ok, good_why = E.check_fields(live[0]["after"])
    print(
        f"fired_on_stripped_next={not stripped_ok} ({stripped_why}) "
        f"silent_on_good={good_ok} ({good_why})"
    )
    if stripped_ok or not good_ok:
        fail = True

    samples_doc = json.loads(SAMPLES.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in D.samples(design)}
    for cap in samples_doc["samples"]:
        author = S.transcribe_author(cap)
        indep = S.transcribe_independent(cap)
        rec = by_id.get(cap["id"]) or {}
        ok, why = S.same_verdict(author, indep)
        rec_ok = rec.get("verdict") == "EXPRESSIBLE" == author.get("verdict")
        print(
            f"sample id={cap['id']} author={author.get('verdict')} "
            f"indep={indep.get('verdict')} recorded={rec.get('verdict')} match={ok and rec_ok}"
        )
        if not ok or not rec_ok:
            fail = True
            print(f"  why={why}")
    neg = S.transcribe_author(samples_doc["negative_control"])
    token = "subsystem-portal-bypasses-command-cockpit-catalog"
    neg_ok = neg.get("verdict") == "INEXPRESSIBLE" and token in str(
        neg.get("first_construct")
    )
    print(f"negative verdict={neg.get('verdict')} construct={neg.get('first_construct')}")
    if not neg_ok:
        fail = True

    if fail:
        print("FAILED:ARC-0052-probe2 error-contract conformance")
        return 1
    print("SUCCESS:ARC-0052-probe2 error-contract conformance sample")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
