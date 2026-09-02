#!/usr/bin/env python3
"""Named probe 1: HONEST-NULL both-states + no inferred pipeline.

Positive: a source with no declared stages yields HONEST-NULL.
Negative: a source with declared stages yields a typed list, not null.
Mutation: pipeline_hint / prose verbs must not become stages.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from extractor import HONEST_NULL, extract, is_honest_null  # noqa: E402
from score import load_corpus  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0036-extract-stages.json"
UNIT = "WFA-0036"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if "SUCCESS:WFA-0036" not in blob:
        return fail("sentinel absent")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    corpus = {r["id"]: r for r in load_corpus()}
    null_ids = [
        "g03-json-no-stages",
        "g04-json-empty-stages",
        "g08-js-no-phase",
        "g10-md-prose-only",
        "g20-json-hint-only",
    ]
    present_ids = [
        "g01-json-two-stage",
        "g02-json-fanout-3",
        "g06-js-three-phase",
        "g09-md-stages",
        "g16-json-four-stage",
    ]
    for rid in null_ids:
        got = extract(corpus[rid]["native"])
        if not is_honest_null(got):
            return fail("declared-absent source produced stages", {"id": rid, "got": got})
    for rid in present_ids:
        got = extract(corpus[rid]["native"])
        if is_honest_null(got) or not isinstance(got, list) or not got:
            return fail("declared-present source yielded HONEST-NULL", {"id": rid, "got": got})

    hinted = extract(corpus["g20-json-hint-only"]["native"])
    if hinted != HONEST_NULL:
        return fail("pipeline_hint inferred a pipeline", hinted)
    prose = extract(corpus["g10-md-prose-only"]["native"])
    if prose != HONEST_NULL:
        return fail("markdown prose inferred a pipeline", prose)

    mutant = {
        "id": "mutant-prose",
        "does": "First clone, then scan, then merge.",
        "pipeline_hint": ["clone", "scan", "merge"],
        "suggested_pipeline": "clone|scan|merge",
    }
    if not is_honest_null(extract(mutant)):
        return fail("mutant prose/hint inferred stages", extract(mutant))

    art_null = (doc.get("honest_null_controls") or {}).get("absent_source_ids") or []
    if not set(null_ids).issubset(set(art_null)):
        return fail("artifact did not record absent-source controls", art_null)

    payload = {
        "pass": True,
        "probe": "probe1-honest-null-both-states",
        "unit_id": UNIT,
        "absent_ids": null_ids,
        "present_ids": present_ids,
        "hint_not_inferred": True,
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(f"SUCCESS:{UNIT}-probe1 honest-null both-states; hint not inferred")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
