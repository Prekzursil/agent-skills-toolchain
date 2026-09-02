#!/usr/bin/env python3
"""Named probe 1: silent generation, private ranking, aggregation.

Happy path. The delivered-prompt scan must be SILENT. Aggregation from
the session must match an independent Borda recompute from raw ballots.
Ranking prompts delivered after an early ballot must still omit that
ballot (mid-stream privacy).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from council.protocol.ngt import (  # noqa: E402
    aggregate_ballots,
    catalog_block,
    scan_delivered_prompts,
    scan_generation_privacy,
)
from scenario import run_session  # noqa: E402


def local_borda(catalog_ids: list[str], rankings: dict[str, list[str]]) -> dict[str, int]:
    """Independent Borda (not session.aggregate, not stored scores)."""
    n = len(catalog_ids)
    scores = {idea_id: 0 for idea_id in catalog_ids}
    for ranking in rankings.values():
        for place, idea_id in enumerate(ranking):
            scores[idea_id] += n - place
    return scores


def main() -> int:
    packed = run_session(leak=None, midstream_rank=True)
    session = packed["session"]
    gen_priv = scan_generation_privacy(session)
    rank_scan = scan_delivered_prompts(session, before_aggregation=True)

    if gen_priv["fired"]:
        print(
            "FAILED:IMP-0332-probe1 generation prompt contained peer idea text "
            f"findings={gen_priv['findings']}"
        )
        return 1
    after = packed["gen_after_alice"]["body"]
    alice_ideas = session.pending_ideas["alice"]
    for text in alice_ideas:
        if text in after:
            print(
                "FAILED:IMP-0332-probe1 bob generation prompt after alice submit "
                f"contains {text!r}"
            )
            return 1

    if rank_scan["fired"]:
        print(
            "FAILED:IMP-0332-probe1 ranking leak on clean run "
            f"findings={rank_scan['findings']}"
        )
        return 1

    sections = session.ranking_prompt_catalog_sections()
    expected_block = catalog_block(session.ranking_catalog_rows())
    if len(sections) != 3:
        print(f"FAILED:IMP-0332-probe1 expected 3 ranking catalog sections, got {len(sections)}")
        return 1
    for pid, inner in sections.items():
        if inner != expected_block:
            print(f"FAILED:IMP-0332-probe1 catalog section mismatch for {pid}")
            return 1
        if "author_id" in inner or "author=" in inner:
            print(f"FAILED:IMP-0332-probe1 author field leaked into {pid} catalog")
            return 1

    bob_body = packed["ranking_prompts"]["bob"]["body"]
    alice_ballot = session.ballots["alice"]
    for needle in alice_ballot["needles"]:
        if needle in bob_body:
            print(
                "FAILED:IMP-0332-probe1 bob ranking prompt contains alice needle "
                f"{needle!r} after alice already ranked"
            )
            return 1

    result = session.aggregate()
    raw = session.raw_ballots()
    ids = session.catalog_ids()
    independent = aggregate_ballots(ids, raw)
    local = local_borda(ids, raw)
    if independent["scores"] != result["scores"] or independent["order"] != result["order"]:
        print(
            "FAILED:IMP-0332-probe1 independent aggregate_ballots mismatch "
            f"session={result} independent={independent}"
        )
        return 1
    if local != result["scores"]:
        print(
            f"FAILED:IMP-0332-probe1 local Borda mismatch session={result['scores']} local={local}"
        )
        return 1

    doc = {
        "probe": "probe1-silent-private-aggregate",
        "unit_id": "IMP-0332",
        "pass": True,
        "generation_scan_fired": gen_priv["fired"],
        "ranking_scan_fired": rank_scan["fired"],
        "scanned_pre_aggregation_prompts": rank_scan["scanned_prompt_count"],
        "catalog_sections_identical": True,
        "midstream_alice_ballot_absent_from_bob": True,
        "aggregation_method": result["method"],
        "ballots_used": result["ballots_used"],
        "scores": result["scores"],
        "order": result["order"],
        "independent_scores_match": True,
        "local_borda_match": True,
        "participants": session.participant_ids,
        "idea_count": len(ids),
    }
    print(json.dumps(doc, sort_keys=True))
    print(
        "generation_silent=True ranking_scan_silent=True "
        f"borda_match=True order={result['order']}"
    )
    print("SUCCESS:IMP-0332-probe1 silent generation, private ranking, aggregation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
