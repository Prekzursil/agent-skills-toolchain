#!/usr/bin/env python3
"""Probe 2: independent nearest-sibling differential; planted duplicate caught."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import family as F  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0104-probe2 {msg}")
    return 1


def main() -> int:
    art_path = REPO / F.OUT_REL
    if not art_path.is_file():
        return fail("artifact missing")
    doc = json.loads(art_path.read_text(encoding="utf-8"))
    body = F.artifact_body(doc)
    presets = [p for p in (body.get("presets") or []) if isinstance(p, dict)]
    if len(presets) != 2:
        return fail(f"preset count {len(presets)}")

    catalog = F.load_catalog()
    if len(catalog) < 2:
        return fail("catalog fixture too small")

    live = {}
    for p in presets:
        sib = F.nearest_sibling(p, catalog)
        live[p["id"]] = sib
        named = sib.get("named")
        if not named:
            return fail(f"no sibling named for {p.get('id')}")
        if sib.get("same_mechanism") or int(sib.get("distance") or 0) < 1:
            return fail(f"{p.get('id')} is a mechanism-duplicate of {named}")
        if not sib.get("axes_that_differ"):
            return fail(f"{p.get('id')} differential empty vs {named}")

    recorded = body.get("nearest_sibling") or {}
    for pid, sib in live.items():
        rec = recorded.get(pid) or {}
        if rec.get("named") != sib.get("named"):
            return fail(f"sibling name drift {pid}: live={sib.get('named')} rec={rec.get('named')}")
        if rec.get("distance") != sib.get("distance"):
            return fail(f"sibling distance drift {pid}")

    critique = next(p for p in presets if "design-plan-critique" in p["id"])
    gng = next(p for p in presets if "release-go-no-go" in p["id"])
    if not F.split_holds(critique, gng):
        return fail("split criterion does not hold between family members")
    intra = F.axis_distance(F.mechanism_tuple(critique), F.mechanism_tuple(gng))
    if intra < 2:
        return fail(f"intra-family distance {intra}")

    planted = F.name_only_clone(critique, "NEG.planted-duplicate", "totally-new-name")
    planted_dist = F.axis_distance(F.mechanism_tuple(critique), F.mechanism_tuple(planted))
    if planted_dist != 0:
        return fail(f"planted rename was not distance 0 ({planted_dist})")
    caught = F.nearest_sibling(planted, [critique] + catalog)
    if not caught.get("same_mechanism") or caught.get("named") != critique["id"]:
        return fail(f"planted duplicate not caught {caught}")

    named_critique = live[critique["id"]]["named"]
    named_gng = live[gng["id"]]["named"]
    print(
        json.dumps(
            {
                "reviewer": "CNL-0104-probe2-independent-re-tabulation",
                "independent": True,
                "method": "axis_distance(mechanism_tuple) over catalog_fixture.json; name ignored",
                "critique_nearest_sibling": named_critique,
                "critique_distance": live[critique["id"]]["distance"],
                "critique_axes_that_differ": live[critique["id"]]["axes_that_differ"],
                "gonogo_nearest_sibling": named_gng,
                "gonogo_distance": live[gng["id"]]["distance"],
                "gonogo_axes_that_differ": live[gng["id"]]["axes_that_differ"],
                "intra_family_distance": intra,
                "split_holds": True,
                "planted_duplicate_distance": planted_dist,
                "planted_duplicate_caught": True,
            },
            indent=2,
        )
    )
    print(
        f"sibling critique={named_critique} d={live[critique['id']]['distance']} "
        f"gng={named_gng} d={live[gng['id']]['distance']} planted_caught=True"
    )
    print("SUCCESS:CNL-0104-probe2 sibling-differential planted-duplicate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
