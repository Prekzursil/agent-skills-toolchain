#!/usr/bin/env python3
"""Named probe 2: nearest-sibling differential, independent of the author's claim."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from preset import fingerprint, preset as load_preset  # noqa: E402
from siblings import nearest  # noqa: E402

ART_REL = (
    "command-center/design/council/"
    "CNL-0110-requirements-council-elicitation-plus-conflict-reconciliat.md"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0110-probe2 {msg}")
    return 1


def main() -> int:
    art_path = REPO / ART_REL
    if not art_path.is_file():
        return fail("artifact missing")
    doc = json.loads(art_path.read_text(encoding="utf-8"))
    live = nearest(fingerprint(load_preset()))
    named = live["nearest_twelve_council_sourced"]
    if named is None:
        return fail("no 12-COUNCIL-sourced sibling on disk")
    if named["id"] != "council.preset.catalog-class.editable":
        return fail(f"nearest sourced sibling {named['id']}")
    if named["distance"] < 3:
        return fail(
            f"distance {named['distance']} axes={named['axes_differ']} "
            "(name-only change would score 0; need a mechanism delta)"
        )
    claimed = doc.get("nearest_sibling") or {}
    if claimed.get("named") != named["id"]:
        return fail(f"artifact named {claimed.get('named')} live named {named['id']}")
    if int(claimed.get("distance") or -1) != named["distance"]:
        return fail("artifact distance drifted from live recompute")
    planted = live["planted_duplicate"]
    if planted["distance"] != 0:
        return fail(f"name-clone distance {planted['distance']} (want 0)")
    differ = set(named["axes_differ"])
    for axis in ("role_set", "phase_split", "unreconcilable_outcome"):
        if axis not in differ:
            return fail(f"{axis} did not differ from catalog-class.editable")
    if live["library"]["twelve_council_present"]:
        return fail("library unexpectedly present; recompute over the 72")

    print(
        json.dumps(
            {
                "probe": "probe2-sibling-differential",
                "named": named["id"],
                "source": named["source"],
                "distance": named["distance"],
                "axes_differ": named["axes_differ"],
                "planted_clone_distance": planted["distance"],
                "library_present": live["library"]["twelve_council_present"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNL-0110-probe2 nearest-sibling differential")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
