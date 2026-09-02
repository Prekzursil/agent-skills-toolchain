#!/usr/bin/env python3
"""Probe 2: use-versus-mention — documenting a mechanism is not implementing it.

Both-states: the same extractor with notes folded into definition fields MUST
credit the documented barrier; the real definition scan MUST NOT.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from extractor import (  # noqa: E402
    extract_from_definition,
    extract_from_prose,
    mention_only_fixture,
)

ART = REPO / "command-center" / "wfa" / "WFA-0059-mechanism-extraction.json"
SENTINEL = "SUCCESS:WFA-0059"
BARRIER = "mech:blocking-fan-in-barrier"
HUMAN = "mech:human-checkpoint"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0059-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel-absent")

    fx = mention_only_fixture()
    implemented = extract_from_definition(fx)
    with_notes = extract_from_definition(fx, include_notes=True)
    prose = extract_from_prose(fx)

    if BARRIER in implemented:
        return fail("documented barrier credited as implementation")
    if HUMAN not in implemented:
        return fail(f"human checkpoint missing from definition ids={implemented}")
    if BARRIER not in with_notes:
        return fail("both-states: notes-as-definition did not credit the barrier")
    if HUMAN not in with_notes:
        return fail("both-states lost the implemented checkpoint")

    recorded = doc.get("use_versus_mention") or {}
    if recorded.get("credited_documented_barrier") is not False:
        return fail("artifact did not record mention refusal")
    if recorded.get("notes_would_credit_barrier") is not True:
        return fail("artifact did not record both-states fire")
    if recorded.get("definition_ids") != implemented:
        return fail("artifact definition_ids drifted")

    print(f"implemented={implemented}")
    print(f"prose={prose}")
    print(f"with_notes={with_notes}")
    print(f"barrier_in_impl={BARRIER in implemented} barrier_in_notes={BARRIER in with_notes}")
    print(
        "SUCCESS:WFA-0059-probe2 use-versus-mention refused; "
        "both-states notes-as-definition fired"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
