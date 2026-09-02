#!/usr/bin/env python3
"""Probe 1: pairwise exclusive polarities with both spans quoted.

Both-states: the exclusive detector emits the known collision pair and the
planted same-time pair; it is silent on M-16 homonyms and on same-polarity
MECH-12. The always-pair mutant is rejected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import claims as CL  # noqa: E402
import graph as G  # noqa: E402
import pairwise as P  # noqa: E402

ART = REPO / "command-center" / "audit" / "AUD-0070-contradiction-edge-extraction.json"
UNIT = "AUD-0070"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def evaluate() -> dict:
    built = G.build()
    claims = built["loaded"]["claims"]
    cands = built["candidates"]
    mutant = P.candidates(claims, always=True)
    known = P.pair_in(cands, CL.KNOWN_A, CL.KNOWN_B)
    planted = P.pair_in(cands, CL.PLANT_SAME_A, CL.PLANT_SAME_B)
    later = P.pair_in(cands, CL.PLANT_LATER_A, CL.PLANT_LATER_B)
    homonym = P.pair_in(cands, CL.HOMONYM_A, CL.HOMONYM_B)
    compat = P.pair_in(cands, CL.COMPAT_A, CL.COMPAT_B)
    quoted = all(
        isinstance(c.get("left_span"), str)
        and len(c["left_span"]) >= 8
        and isinstance(c.get("right_span"), str)
        and len(c["right_span"]) >= 8
        for c in cands
    )
    payload = {
        "probe": "probe1-pairwise",
        "unit_id": UNIT,
        "n_claims": len(claims),
        "n_candidates": len(cands),
        "n_mutant_pairs": len(mutant),
        "known_pair_emitted": known is not None,
        "planted_same_time_emitted": planted is not None,
        "planted_later_emitted": later is not None,
        "homonym_silent": homonym is None,
        "compat_silent": compat is None,
        "spans_quoted": quoted,
        "mutant_overclaims": len(mutant) > len(cands),
        "known": known,
        "planted_same_time": planted,
    }
    payload["pass"] = bool(
        known
        and planted
        and later
        and homonym is None
        and compat is None
        and quoted
        and len(mutant) > len(cands)
        and len(cands) >= 3
    )
    return payload


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:AUD-0070" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")

    payload = evaluate()
    print(json.dumps(payload, sort_keys=True, default=str))
    if not payload["pass"]:
        return fail("pairwise detector did not discriminate")
    edges = doc.get("edges") or []
    art_ids = {e.get("id") for e in edges if isinstance(e, dict)}
    if payload["known"] and payload["known"]["id"] not in art_ids:
        return fail("known pair missing from artifact edges")
    print(
        f"candidates={payload['n_candidates']} mutant={payload['n_mutant_pairs']} "
        f"known={payload['known_pair_emitted']} homonym_silent={payload['homonym_silent']}"
    )
    print("SUCCESS:AUD-0070-probe1 pairwise exclusive polarities with quoted spans")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
