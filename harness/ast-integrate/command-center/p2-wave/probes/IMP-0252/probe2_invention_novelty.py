#!/usr/bin/env python3
"""Probe 2: invention scored for novelty against library fingerprints, not counted.

Controls:
  reworded duplicate of an incumbent -> NOT-NOVEL, score 0
  structurally distinct candidate    -> NOVEL
  ten copies of the duplicate        -> volume_count=10 but scores stay 0
                                        (a volume grader would inflate)
  rename-invariance                  -> fingerprint unchanged after id/title rewrite
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center/library/knowledge_blueprints"
sys.path.insert(0, str(LIB))

from fingerprint import mechanism_fingerprint, rename_identifiers  # noqa: E402
from invention import (  # noqa: E402
    grade_candidate,
    grade_inventions,
    novel_morphology_candidate,
    reworded_duplicate,
)
from registry import load_library  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0252.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0252-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:IMP-0252" not in json.dumps(doc):
        return fail("sentinel-absent")

    lib = load_library()
    packs = lib["packs"]
    fps = lib["fingerprints"]
    if len(set(fps.values())) != 4:
        return fail(f"fingerprint collisions among 4 packs: {fps}")
    if lib["fingerprint_collisions"] != 0:
        return fail("registry reported collisions")

    docv = next(p for p in packs if p["id"] == "documentation-verification")
    renamed = rename_identifiers(docv["workflow"], "-alias")
    if mechanism_fingerprint(renamed) != fps["documentation-verification"]:
        return fail("rename changed fingerprint (not mechanism-level)")

    dup = reworded_duplicate(docv)
    dup_grade = grade_candidate(dup, packs)
    if dup_grade["volume_used"]:
        return fail("duplicate grade used volume")
    if dup_grade["verdict"] != "NOT-NOVEL":
        return fail(f"reworded duplicate verdict={dup_grade['verdict']}")
    if dup_grade["novelty_score"] != 0.0 or dup_grade["max_jaccard"] != 1.0:
        return fail(
            f"duplicate score={dup_grade['novelty_score']} jaccard={dup_grade['max_jaccard']}"
        )
    if dup_grade["nearest_id"] != "documentation-verification":
        return fail(f"nearest={dup_grade['nearest_id']}")

    novel = novel_morphology_candidate()
    novel_grade = grade_candidate(novel, packs)
    if novel_grade["volume_used"]:
        return fail("novel grade used volume")
    if novel_grade["verdict"] != "NOVEL":
        return fail(f"distinct candidate verdict={novel_grade['verdict']} score={novel_grade['novelty_score']}")
    if novel_grade["novelty_score"] < 0.5:
        return fail(f"distinct candidate too similar score={novel_grade['novelty_score']}")
    if novel_grade["candidate_fingerprint"] == fps["documentation-verification"]:
        return fail("novel fingerprint collided with documentation-verification")

    flood = grade_inventions([dup] * 10, packs)
    if flood["volume_count"] != 10:
        return fail(f"volume_count={flood['volume_count']}")
    if flood["volume_used_in_score"]:
        return fail("volume mixed into score")
    if flood["max_novelty"] != 0.0 or flood["novel_count"] != 0:
        return fail(
            f"volume flood inflated novelty max={flood['max_novelty']} novel_count={flood['novel_count']}"
        )
    if flood["max_novelty"] == flood["volume_count"]:
        return fail("score equals volume_count — counted instead of fingerprinted")

    # Mixing one novel + nine duplicates: a volume counter still sees 10;
    # fingerprint grading must report novel_count==1 and max_novelty from the one.
    mixed = grade_inventions([dup] * 9 + [novel], packs)
    if mixed["volume_count"] != 10:
        return fail("mixed volume_count")
    if mixed["novel_count"] != 1:
        return fail(f"mixed novel_count={mixed['novel_count']} (volume grader cannot isolate)")
    if mixed["max_novelty"] != novel_grade["novelty_score"]:
        return fail("mixed max_novelty drifted")

    out = {
        "probe": "probe2-invention-novelty",
        "unit_id": "IMP-0252",
        "library_fingerprints": 4,
        "collisions": 0,
        "rename_invariant": True,
        "duplicate_verdict": dup_grade["verdict"],
        "duplicate_score": dup_grade["novelty_score"],
        "novel_verdict": novel_grade["verdict"],
        "novel_score": novel_grade["novelty_score"],
        "volume_count_flood": flood["volume_count"],
        "volume_used": False,
        "flood_max_novelty": flood["max_novelty"],
        "mixed_novel_count": mixed["novel_count"],
        "method": "fingerprint-jaccard",
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"dup score={dup_grade['novelty_score']} novel={novel_grade['novelty_score']} "
        f"flood_vol={flood['volume_count']} flood_max={flood['max_novelty']} "
        f"mixed_novel={mixed['novel_count']}"
    )
    print("SUCCESS:IMP-0252-probe2 invention novelty vs library fingerprints (not volume)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
