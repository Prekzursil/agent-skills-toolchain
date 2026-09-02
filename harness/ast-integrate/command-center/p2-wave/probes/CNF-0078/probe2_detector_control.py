#!/usr/bin/env python3
"""Probe 2: re-run the detector control on the known-broken full-rewrite fixture.

A reviewer who only re-reads the artifact has verified nothing. This probe
recomputes scores on fixtures/detector_control.json, checks the artifact
schema, and confirms flagged pairs carry both scores (dropping one fails).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import checker as C  # noqa: E402
import measures as M  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0078-distinctness-remeasure.json"
SCHEMA = REPO / "command-center/schema/similarity-report.schema.json"
CTRL = HERE / "fixtures" / "detector_control.json"


def main() -> int:
    ctrl = json.loads(CTRL.read_text(encoding="utf-8"))
    scored = M.score_pair(ctrl["a"]["text"], ctrl["b"]["text"])
    expect = ctrl["expect"]
    print(
        f"control lex={scored['lexical_score']} fired={scored['lexical_fired']} "
        f"emb={scored['embedding_score']} fired={scored['embedding_fired']}"
    )
    if scored["lexical_fired"] != expect["lexical_fired"]:
        print("FAILED:CNF-0078-probe2 control lexical fire mismatch")
        return 1
    if scored["embedding_fired"] != expect["embedding_fired"]:
        print("FAILED:CNF-0078-probe2 control embedding fire mismatch")
        return 1
    if not scored["embedding_fired"] or scored["lexical_fired"]:
        print("FAILED:CNF-0078-probe2 detector did not fire as required on known rewrite")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0078-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        print(f"FAILED:CNF-0078-probe2 schema errors n={len(errs)}")
        print(" ", errs[0].message)
        return 1

    garbage = {"totally": "unrelated", "passing_tests": 999999}
    try:
        jsonschema.Draft7Validator(schema).validate(garbage)
    except jsonschema.ValidationError:
        print("schema_rejects_garbage=True")
    else:
        print("FAILED:CNF-0078-probe2 schema accepted garbage")
        return 1

    ok, why = C.flagged_pairs_honest(doc)
    print(f"flagged_honest={ok} {why}")
    if not ok:
        print("FAILED:CNF-0078-probe2 flagged pairs not honest")
        return 1
    ok, why = C.firing_pattern_matches_mutants(doc)
    print(f"mutant_pattern={ok} {why}")
    if not ok:
        print("FAILED:CNF-0078-probe2 mutant pattern mismatch")
        return 1

    mutant = copy.deepcopy(doc)
    if not mutant.get("flagged_pairs"):
        print("FAILED:CNF-0078-probe2 no flagged pairs to mutate")
        return 1
    del mutant["flagged_pairs"][0]["embedding_score"]
    mok, mwhy = C.flagged_pairs_honest(mutant)
    print(f"mutant_dropped_embedding_score accepted={mok} {mwhy}")
    if mok:
        print("FAILED:CNF-0078-probe2 friendlier-score mutant was accepted")
        return 1

    scopes = [m.get("cannot_see") for m in doc.get("measures") or []]
    if len(scopes) < 2 or any(not s or len(str(s)) < 24 for s in scopes):
        print("FAILED:CNF-0078-probe2 measure scopes missing")
        return 1

    print("SUCCESS:CNF-0078-probe2 detector control fired; both-scores checker holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
