#!/usr/bin/env python3
"""Probe 2: mutation must go red; independent recompute of the headline rate.

Does not re-check negative-control agreement (that is probe 1). Recomputes the
refuted fraction from sealed answers + live observers and requires the mutation
extractor to fail on an inverted scratch copy.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import blind as B  # noqa: E402
import questions as Q  # noqa: E402
import study as S  # noqa: E402

ART = REPO / S.OUT_REL
SCHEMA = REPO / S.SCHEMA_REL
SEALED = HERE / "fixtures" / "sealed_answers.json"


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0132-probe2 {msg}")
    return 1


def main() -> int:
    src = (HERE / "blind.py").read_text(encoding="utf-8")
    if "sealed_answers" in src:
        return fail("blind.py mentions sealed_answers")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    if list(validator.iter_errors(doc)):
        return fail("schema-live")
    for garbage in ({"totally": "unrelated"}, {"blob": "x" * 200}, {}):
        if not list(validator.iter_errors(garbage)):
            return fail(f"schema-accepted-garbage {list(garbage)[:1]}")

    sealed = json.loads(SEALED.read_text(encoding="utf-8"))["answers"]
    live_mut = S.mutation_control(sealed)
    print(
        f"mutation live_match={live_mut['live_matches_agreed']} "
        f"mutant_match={live_mut['mutant_matches_agreed']} "
        f"went_red={live_mut['went_red']} mutant={live_mut['mutant_observed']}"
    )
    if not live_mut["went_red"]:
        return fail("mutation-did-not-go-red")
    if live_mut["mutant_matches_agreed"]:
        return fail("mutant-still-matches")
    if not live_mut["live_matches_agreed"]:
        return fail("live-no-longer-matches")
    art_mut = doc.get("mutation_control") or {}
    if art_mut.get("went_red") is not True:
        return fail("artifact-mutation-flag")
    if art_mut.get("mutant_observed") != live_mut["mutant_observed"]:
        return fail("mutation-drift")

    # Independent headline: sealed vs live observers, high-confidence only.
    refuted = held = incon = 0
    for q in Q.QUESTIONS:
        if q["stratum"] != "HIGH-CONFIDENCE-AGREED-UNTESTED":
            continue
        observed = B.observe(REPO, q["id"])
        agreed = sealed[q["id"]]
        verdict = S.verdict_for(agreed, observed)
        print(f"recompute {q['id']} agreed={agreed} observed={observed} verdict={verdict}")
        if verdict == "AGREEMENT-REFUTED":
            refuted += 1
        elif verdict == "AGREEMENT-HELD":
            held += 1
        else:
            incon += 1
    n = refuted + held + incon
    if n != doc["headline"]["n"]:
        return fail(f"headline-n art={doc['headline']['n']} live={n}")
    if refuted != doc["headline"]["refuted"] or held != doc["headline"]["held"]:
        return fail(f"headline-drift refuted={refuted} held={held}")
    if incon != 0:
        return fail(f"inconclusive {incon}")
    if n < 3:
        return fail("high-confidence-n")
    fraction = refuted / n
    recorded = float(doc["headline"]["refuted_fraction"])
    if abs(fraction - recorded) > 1e-5:
        return fail(f"fraction-drift live={fraction} art={recorded}")
    print(
        f"headline refuted={refuted}/{n} fraction={fraction:.6f} "
        f"wilson={doc['headline']['interval_95']}"
    )
    print("SUCCESS:ADV-0132-probe2 mutation went red; independent headline recomputed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
