#!/usr/bin/env python3
"""Probe 1: implicit stays IMPLICIT; council-only roles stay in the council bucket.

Naive mutants: promote implicit to DECLARED; bleed 11/12 roles onto candidates.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402

OUT = REPO / "command-center/wfa/WFA-0037-extract-roles.json"
IMPLICIT_CAND = "wf-implicit-reviewer"
COUNCIL_ONLY = ("owner-veto", "juror")


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0037-probe1 {msg}")
    return 1


def by_id(rows: list[dict]) -> dict[str, dict]:
    return {str(r.get("candidate_id")): r for r in rows}


def candidate_role_ids(rows: list[dict]) -> set[str]:
    ids: set[str] = set()
    for row in rows:
        for role in row.get("roles") or []:
            ids.add(str(role.get("id") or "").lower())
    return ids


def main() -> int:
    if not OUT.is_file():
        return fail("artifact-missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    text = OUT.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0037" not in text:
        return fail("sentinel-absent")

    rows = doc.get("per_candidate") or []
    table = by_id(rows)
    if IMPLICIT_CAND not in table:
        return fail("implicit-candidate-missing")
    impl = table[IMPLICIT_CAND]
    impl_roles = impl.get("roles") or []
    if not impl_roles:
        return fail("implicit-candidate-has-no-roles")
    reviewer = next((r for r in impl_roles if str(r.get("id")).lower() == "reviewer"), None)
    if reviewer is None:
        return fail(f"reviewer-not-extracted roles={[r.get('id') for r in impl_roles]}")
    if reviewer.get("origin") != "IMPLICIT":
        return fail(f"implicit-promoted-to-declared origin={reviewer.get('origin')}")
    inference = reviewer.get("inference") or ""
    if "reviewer" not in inference.lower() or "vote" not in inference.lower():
        return fail(f"inference-missing {inference!r}")
    if impl.get("fill") != "IMPLICIT":
        return fail(f"fill-not-implicit {impl.get('fill')}")

    council = {str(r.get("id")).lower() for r in (doc.get("council_bucket") or [])}
    for need in COUNCIL_ONLY:
        if need not in council:
            return fail(f"council-role-not-bucketed {need} bucket={sorted(council)}")
    cand_ids = candidate_role_ids(rows)
    for banned in COUNCIL_ONLY:
        if banned in cand_ids:
            return fail(f"council-role-bled-onto-candidate {banned}")

    honest = E.extract_root(E.FIXTURE_CORPUS, mode="honest")
    bleed = E.extract_root(E.FIXTURE_CORPUS, mode="bleed_council")
    promo = E.extract_root(E.FIXTURE_CORPUS, mode="promote_implicit")
    honest_ids = candidate_role_ids(honest["candidates"])
    bleed_ids = candidate_role_ids(bleed["candidates"])
    if "owner-veto" in honest_ids:
        return fail("honest-already-bleeds-owner-veto")
    if "owner-veto" not in bleed_ids:
        return fail("bleed-mutant-did-not-copy-owner-veto")
    promo_impl = by_id(promo["candidates"]).get(IMPLICIT_CAND) or {}
    promo_rev = next(
        (r for r in (promo_impl.get("roles") or []) if str(r.get("id")).lower() == "reviewer"),
        None,
    )
    if promo_rev is None or promo_rev.get("origin") != "DECLARED" or promo_rev.get("inference"):
        return fail("promote-mutant-did-not-fire")
    print(
        "implicit origin=IMPLICIT inference_stated=True "
        f"council_bucket={sorted(council)} "
        "bleed_mutant_owner-veto=True promote_mutant_declared=True"
    )
    print("SUCCESS:WFA-0037-probe1 implicit-and-council-bucket")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
