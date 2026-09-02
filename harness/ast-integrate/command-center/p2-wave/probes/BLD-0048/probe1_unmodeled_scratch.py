#!/usr/bin/env python3
"""Control: delete one actor from a scratch copy of the model set → UNMODELED."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402

COMPLETE = HERE / "fixtures" / "complete-phase12-model.md"
DECOY = HERE / "fixtures" / "decoy-no-actors.md"
STRIP_ID = "curious-insider-reading-artifacts"


def main() -> int:
    complete = COMPLETE.read_text(encoding="utf-8")
    decoy = DECOY.read_text(encoding="utf-8")
    actor = C.actor_by_id(STRIP_ID)

    decoy_hits = C.classify_actors(
        [{"path": "decoy", "text": decoy, "source": "decoy"}],
        tests=[],
        searched_paths=["decoy"],
    )
    if any(r["verdict"] != "UNMODELED" for r in decoy_hits):
        print("FAILED:BLD-0048-probe1 decoy document modeled an actor")
        return 1

    full_docs = [
        {
            "path": "fixtures/complete-phase12-model.md",
            "text": complete,
            "source": "scratch-complete",
        }
    ]
    full = C.classify_actors(full_docs, tests=[], searched_paths=[full_docs[0]["path"]])
    if any(r["verdict"] == "UNMODELED" for r in full):
        bad = [r["id"] for r in full if r["verdict"] == "UNMODELED"]
        print("FAILED:BLD-0048-probe1 complete fixture left UNMODELED " + ",".join(bad))
        return 1
    if any(r["verdict"] != "MODELED-BUT-UNTESTED" for r in full):
        print("FAILED:BLD-0048-probe1 complete fixture should be MODELED-BUT-UNTESTED (no B08/B10 probes in scratch)")
        return 1
    if not C.modeled_ok(full):
        print("FAILED:BLD-0048-probe1 modeled_ok failed on complete fixture")
        return 1

    stripped = C.strip_actor_text(complete, actor)
    if C.hits_in(stripped, actor["phrases"]):
        print("FAILED:BLD-0048-probe1 strip left a phrase behind")
        return 1
    stripped_docs = [
        {
            "path": "fixtures/complete-phase12-model.md#stripped",
            "text": stripped,
            "source": "scratch-stripped",
        }
    ]
    after = C.classify_actors(
        stripped_docs, tests=[], searched_paths=[stripped_docs[0]["path"]]
    )
    by_id = {r["id"]: r for r in after}
    if by_id[STRIP_ID]["verdict"] != "UNMODELED":
        print(
            "FAILED:BLD-0048-probe1 stripped actor verdict="
            + by_id[STRIP_ID]["verdict"]
        )
        return 1
    miss = by_id[STRIP_ID]["evidence"]
    if miss.get("kind") != "search-miss" or not miss.get("paths_searched"):
        print("FAILED:BLD-0048-probe1 UNMODELED missing search evidence")
        return 1
    others = [r for r in after if r["id"] != STRIP_ID]
    if any(r["verdict"] == "UNMODELED" for r in others):
        bad = [r["id"] for r in others if r["verdict"] == "UNMODELED"]
        print("FAILED:BLD-0048-probe1 strip over-deleted " + ",".join(bad))
        return 1

    print(
        f"stripped_actor={STRIP_ID} verdict=UNMODELED "
        f"complete_unmodeled=0 others_still_modeled={len(others)} "
        f"decoy_unmodeled={len(decoy_hits)}"
    )
    print("SUCCESS:BLD-0048-probe1 scratch-delete → UNMODELED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
