#!/usr/bin/env python3
"""Probe 1: print the three-way intersection and per-vendor unique sets.

The intersection is COMPUTED from dual-rail (E2) feature lists. A planted
vendor-unique primitive must not appear in the intersection (clean). The
same primitive forced into all three lists MUST appear (red mutant).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import captures_lib as C  # noqa: E402
import features as F  # noqa: E402
import intersect as I  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:RES-0031-probe1 {msg}")
    return 1


def main() -> int:
    extracted = F.extract(C.by_id(C.load_metas()))
    lists = extracted["e2_sets"]
    inter = I.intersection(lists)
    uniques = I.unique_sets(lists)
    planted = F.PLANTED_UNIQUE
    print("E2_FEATURE_LISTS " + json.dumps(lists, sort_keys=True))
    print("THREE-WAY INTERSECTION " + json.dumps(inter))
    print("UNIQUE cline " + json.dumps(uniques["cline"]))
    print("UNIQUE roo " + json.dumps(uniques["roo"]))
    print("UNIQUE windsurf " + json.dumps(uniques["windsurf"]))
    print(
        "PRESENCE_ANY_RAIL (not citable as measured fact) "
        + json.dumps(extracted["present_sets"], sort_keys=True)
    )
    if planted in inter:
        return _fail(f"planted unique {planted} leaked into intersection")
    if planted not in lists["roo"]:
        return _fail(f"control unique {planted} missing from Roo E2 list")
    if planted in lists["cline"] or planted in lists["windsurf"]:
        return _fail(f"control unique {planted} is not Roo-only")
    mutant = I.mutate_plant_into_all(lists, planted)
    mutant_inter = I.intersection(mutant)
    print(f"RED_MUTANT intersection_contains_planted={planted in mutant_inter}")
    if planted not in mutant_inter:
        return _fail("detector silent: planted unique did not enter mutant intersection")
    if len(inter) < 1:
        return _fail("empty E2 intersection; extractor may be silent in both states")
    required = {"mcp-json-mcpservers", "mcp-stdio", "mcp-remote-http"}
    missing = sorted(required - set(inter))
    if missing:
        return _fail(f"expected MCP portable core missing: {missing}")
    forbidden = {"custom-modes", "first-class-memories", "memory-bank-methodology", "hooks"}
    leaked = sorted(set(inter) & forbidden)
    if leaked:
        return _fail(f"vendor-unique primitives in intersection: {leaked}")
    print("SUCCESS:RES-0031-probe1 three-way intersection and unique sets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
