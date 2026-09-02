"""Independent recount / re-tabulation reviewer for CNL-0040.

Does not read the author's answer prose. Re-derives family membership from
the catalog parenthetical and the ranging-set fixture, then compares the
artifact's protocol record_ids. A disagreement in the number blocks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import family as F  # noqa: E402
import runtime as R  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0040-executable-runtime-semantics-for-the-6-judicial-protocols.md"


def retabulate(artifact: dict | None = None) -> dict:
    enum = F.enumerate_family()
    cat_ids = list(enum["catalog"]["ids"])
    fix_ids = list(enum["fixture"]["ids"])
    spec_ids = [R.PROTOCOLS[k]["record_id"] for k in sorted(R.PROTOCOLS)]
    art_ids: list[str] = []
    art_n = None
    if artifact is None and ART.is_file():
        artifact = json.loads(ART.read_text(encoding="utf-8"))
    if isinstance(artifact, dict):
        art_n = artifact.get("family_count")
        for p in artifact.get("protocols") or []:
            if isinstance(p, dict) and p.get("record_id"):
                art_ids.append(str(p["record_id"]))
    numbers = {
        "catalog_n": len(cat_ids),
        "fixture_n": len(fix_ids),
        "semantics_n": len(spec_ids),
        "artifact_n": len(art_ids) if artifact is not None else None,
        "artifact_family_count": art_n,
        "expected_n": F.EXPECTED_N,
    }
    sets_equal = cat_ids == fix_ids == spec_ids
    if artifact is not None:
        sets_equal = sets_equal and art_ids == cat_ids
        if art_n is not None and int(art_n) != F.EXPECTED_N:
            sets_equal = False
    disagreement = not (
        numbers["catalog_n"]
        == numbers["fixture_n"]
        == numbers["semantics_n"]
        == F.EXPECTED_N
        and (numbers["artifact_n"] in (None, F.EXPECTED_N))
        and sets_equal
    )
    return {
        "reviewer_id": "CNL-0040-independent-recount",
        "independent": True,
        "scope_not_agreement": True,
        "catalog_ids": cat_ids,
        "fixture_ids": fix_ids,
        "semantics_ids": spec_ids,
        "artifact_ids": art_ids,
        "numbers": numbers,
        "disagreement": disagreement,
        "verdict": "BLOCK" if disagreement else "PASS",
        "method": (
            "Regex-parse CNL-0040 question_or_target P-ids; JSON-load "
            "ranging_set.json members; list runtime.PROTOCOLS keys; list "
            "artifact.protocols[].record_id. Compare sets and counts. "
            "Does not read answer prose."
        ),
    }
