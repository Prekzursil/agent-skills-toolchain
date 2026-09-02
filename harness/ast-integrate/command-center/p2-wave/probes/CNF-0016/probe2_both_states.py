#!/usr/bin/env python3
"""Probe 2: both-states detector, schema garbage, blank-row mutant, RECORD locus."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import check as C  # noqa: E402
import corpus as K  # noqa: E402
import recipe as R  # noqa: E402


def main() -> int:
    try:
        doc = C.load_artifact()
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAILED:CNF-0016-probe2 artifact {type(exc).__name__}: {exc}")
        return 1

    ok_garb, why_garb = C.schema_rejects_garbage()
    print(why_garb)
    if not ok_garb:
        print("FAILED:CNF-0016-probe2", why_garb)
        return 1

    errs = C.validate_doc(doc)
    if errs:
        print("FAILED:CNF-0016-probe2 artifact schema", errs[:12])
        return 1

    ok_mut, why_mut = C.reject_blank_mutant(doc)
    print(why_mut)
    if not ok_mut:
        print("FAILED:CNF-0016-probe2", why_mut)
        return 1

    briefs = [K.strip_brief(d) for d in K.p0_records()]
    for b in briefs:
        hits = K.leak_hits(b)
        if hits:
            print("FAILED:CNF-0016-probe2 leak in brief", b["id"], hits)
            return 1
    raw = K.load_raw_corpus()
    leaked = False
    for d in raw.get("defects") or []:
        unstripped = {
            "id": d.get("id"),
            "implementer_conclusion": d.get("implementer_conclusion"),
        }
        if K.leak_hits(unstripped):
            leaked = True
            break
    if not leaked:
        print("FAILED:CNF-0016-probe2 leak-detector silent on unstripped conclusion")
        return 1
    print("leak-detector: stripped briefs clean; unstripped conclusion flagged")

    live = R.measure_all(briefs)
    ok_states, why_states = C.both_states(live)
    print(why_states)
    if not ok_states:
        print("FAILED:CNF-0016-probe2", why_states)
        return 1
    ok_states_art, why_states_art = C.both_states(C.recipes_of(doc))
    if not ok_states_art:
        print("FAILED:CNF-0016-probe2 artifact", why_states_art)
        return 1

    ok_rec, why_rec = C.record_defects_ok(doc)
    print(why_rec)
    if not ok_rec:
        print("FAILED:CNF-0016-probe2", why_rec)
        return 1

    rev = doc.get("reviewer") or {}
    rep = C.report_of(doc)
    if rev.get("independent") is not True:
        print("FAILED:CNF-0016-probe2 reviewer is agreement-only")
        return 1
    if (
        rep.get("scope_not_agreement") is not True
        and rev.get("scope_not_agreement") is not True
    ):
        print("FAILED:CNF-0016-probe2 reviewer is agreement-only")
        return 1

    print("SUCCESS:CNF-0016-probe2 both-states schema-garbage record-locus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
