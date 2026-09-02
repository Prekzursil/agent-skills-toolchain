#!/usr/bin/env python3
"""Probe 1: typed staged handoff + judge-context census.

Asserts:
  * propose -> critique -> rule kinds and stage order
  * judge view has no proposer_id / reasoning fields
  * planted proposer identity token is absent from the judge census
  * planted unsurfaced reasoning token is absent from the judge census
  * critique-surfaced excerpt IS present (so the census is not vacuously empty)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import fixture as F  # noqa: E402
from tools.council.topology.pcj import STAGES, kinds_of  # noqa: E402

OUT = HERE / "probe1-staged-handoff.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0283-probe1 {msg}")
    return 1


def main() -> int:
    result = F.live_pipeline()
    census = result.census
    view_blob = json.dumps(result.view, sort_keys=True)
    kinds = kinds_of(result)
    stages = [h.stage for h in result.handoff]

    if kinds != [
        "pcj.proposal",
        "pcj.critique",
        "pcj.judge_view",
        "pcj.ruling",
    ]:
        return fail(f"unexpected kinds {kinds}")
    if stages != list(STAGES):
        return fail(f"handoff stages {stages} != {list(STAGES)}")
    if census["identity_leaked"] or census["proposer_id_field_present"]:
        return fail(f"identity leaked hits={census['identity_hits']}")
    if F.PROPOSER_ID in view_blob or F.PROPOSER_ID in json.dumps(census["string_values"]):
        return fail("proposer identity token present in judge view")
    if "Alice-QK7" in view_blob:
        return fail("proposer alias leaked into judge view")
    if census["unsurfaced_reasoning_in_view"] or census["reasoning_field_present"]:
        return fail("unsurfaced reasoning reached the judge")
    if F.UNSURFACED in view_blob:
        return fail("unsurfaced reasoning token present in judge view")
    if F.SURFACED not in view_blob:
        return fail("surfaced critique excerpt missing from judge view (vacuous census)")
    if F.UNSURFACED not in result.proposal.reasoning:
        return fail("fixture reasoning lost the planted token")
    if result.ruling.judge_id == result.proposal.proposer_id:
        return fail("proposer judged their own proposal")
    if not result.citation_check.ok:
        return fail(f"live ruling citation check failed {result.citation_check.to_dict()}")

    payload = {
        "probe": "probe1-staged-handoff",
        "unit_id": F.UNIT,
        "pass": True,
        "kinds": kinds,
        "stages": stages,
        "census": {
            "n_claims": census["n_claims"],
            "n_points": census["n_points"],
            "point_ids": census["point_ids"],
            "identity_leaked": census["identity_leaked"],
            "unsurfaced_reasoning_in_view": census["unsurfaced_reasoning_in_view"],
            "proposer_id_field_present": census["proposer_id_field_present"],
            "reasoning_field_present": census["reasoning_field_present"],
            "field_names": census["field_names"],
        },
        "identity_token_in_judge_view": False,
        "unsurfaced_token_in_judge_view": False,
        "surfaced_excerpt_in_judge_view": True,
        "citation_check_ok": result.citation_check.ok,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(
        "kinds="
        + ",".join(kinds)
        + f" identity_leaked={census['identity_leaked']}"
        + f" unsurfaced={census['unsurfaced_reasoning_in_view']}"
        + f" surfaced={F.SURFACED in view_blob}"
    )
    print("SUCCESS:IMP-0283-probe1 staged-handoff and judge-context census")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
