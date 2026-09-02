#!/usr/bin/env python3
"""Probe 1: blind vs non-blind pairwise distributions must separate.

Also requires the theatre-blind (configured blind, copied briefs) case to
refuse INDEPENDENT_MEASURED. The config flag is not a success predicate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0343.json"
UNIT = "IMP-0343"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    honest = S.blind_versus_nonblind()
    theatre = S.theatre_versus_nonblind()
    print(json.dumps({"honest": honest, "theatre": theatre}, sort_keys=True))

    if not honest["separation"]["separated"]:
        return fail("honest blind vs non-blind did not separate")
    if not honest["independence_achieved"]:
        return fail("honest run did not report independence_achieved")
    if honest["verdict"] != "INDEPENDENT_MEASURED":
        return fail(f"honest verdict {honest['verdict']!r}")
    if honest["blind_token_distribution"]["mean"] >= honest["nonblind_token_distribution"]["mean"]:
        return fail("blind mean was not below non-blind mean")
    if honest["control_shared_phrase_count"] <= honest["claimed_shared_phrase_count"]:
        return fail(
            "non-blind census was not larger than independent census "
            f"{honest['control_shared_phrase_count']} vs "
            f"{honest['claimed_shared_phrase_count']}"
        )
    if honest["configured_blind"]["used_as_success_predicate"]:
        return fail("config flag used as success predicate")
    if not honest["configured_blind"]["claimed_run"]:
        return fail("honest fixture is not configured_blind")

    if theatre["separation"]["separated"]:
        return fail("theatre-blind incorrectly separated from non-blind")
    if theatre["independence_achieved"]:
        return fail("theatre-blind declared independence_achieved from config")
    if theatre["verdict"] != "NOT_INDEPENDENT":
        return fail(f"theatre verdict {theatre['verdict']!r}")
    if not theatre["configured_blind"]["claimed_run"]:
        return fail("theatre fixture lost configured_blind=true")
    if theatre["configured_blind"]["used_as_success_predicate"]:
        return fail("theatre used config flag as success predicate")

    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0343" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    measured = doc.get("measured") or {}
    if measured.get("honest_separated") is not True:
        return fail("receipt honest_separated drift")
    if measured.get("theatre_independence_achieved") is not False:
        return fail("receipt theatre_independence_achieved drift")

    print(
        f"separated={honest['separation']['separated']} "
        f"gap={honest['separation']['gap']:.3f} "
        f"theatre_verdict={theatre['verdict']}"
    )
    print("SUCCESS:IMP-0343-probe1 blind/non-blind separation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
