#!/usr/bin/env python3
"""EXACT tool-surface overlap between measured servers -- the retirement evidence.

The destructive-action default on this estate is explicit: 34 of 57 skill pairs LOOKED
like duplicates and ZERO shared meaningful content.  So a retirement recommendation may
not rest on "they both do browsers".  This computes set arithmetic over the tool-name
surfaces that ``probe_capability.py`` actually measured via ``tools/list``:

  containment   A's names are a SUBSET of B's  -> A is retirement-eligible (reversibly)
  identical     same set both ways             -> pick one, disable the other
  partial       overlap but each has unique    -> INVESTIGATE, never disable

An exact question deserves an algorithm, not judgement: this is set membership, so it is
computed, not inferred.  Whether the divergent content MATTERS is left to prose.

Run: ``python overlap_report.py capability-matrix.json [-o overlap.json]``
"""

from __future__ import annotations

import argparse
import itertools
import json
import pathlib
from typing import Any

MIN_OVERLAP = 1  # report any pair sharing at least one tool name


def load_surfaces(paths: list[pathlib.Path]) -> dict[str, list[str]]:
    """name -> sorted tool names, for every row that a real handshake verified."""
    surfaces: dict[str, list[str]] = {}
    for path in paths:
        blob = json.loads(path.read_text(encoding="utf-8"))
        for row in blob.get("rows", []):
            if row.get("call_verified") and row.get("tool_names"):
                surfaces[row["name"]] = sorted(row["tool_names"])
    return surfaces


def classify(a: set[str], b: set[str]) -> str:
    if a == b:
        return "identical"
    if a < b:
        return "a-contained-in-b"
    if b < a:
        return "b-contained-in-a"
    return "partial"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", default="")
    args = ap.parse_args(argv)

    paths = [pathlib.Path(p) for p in args.inputs]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        print(f"FAILED:overlap-report missing input(s) {missing}")
        return 1
    surfaces = load_surfaces(paths)
    if not surfaces:
        print("FAILED:overlap-report zero verified surfaces (fail closed)")
        return 1

    print(f"== {len(surfaces)} measured tool surfaces ==")
    for name, names in sorted(surfaces.items(), key=lambda kv: -len(kv[1])):
        print(f"  {name:24} {len(names):4} tools")

    pairs: list[dict[str, Any]] = []
    for left, right in itertools.combinations(sorted(surfaces), 2):
        a, b = set(surfaces[left]), set(surfaces[right])
        shared = a & b
        if len(shared) < MIN_OVERLAP:
            continue
        kind = classify(a, b)
        pairs.append(
            {
                "a": left,
                "b": right,
                "a_tools": len(a),
                "b_tools": len(b),
                "shared": len(shared),
                "a_only": sorted(a - b),
                "b_only": sorted(b - a),
                "relation": kind,
                "jaccard": round(len(shared) / len(a | b), 4),
                # A retirement is only defensible on total containment: the contained
                # side loses nothing a caller could still reach.
                "retirement_eligible": (
                    left
                    if kind == "a-contained-in-b"
                    else right
                    if kind == "b-contained-in-a"
                    else None
                ),
            }
        )

    pairs.sort(key=lambda p: (-p["shared"], p["a"], p["b"]))
    print(f"\n== {len(pairs)} overlapping pair(s) ==")
    for p in pairs:
        target = p["retirement_eligible"] or "-none- INVESTIGATE"
        print(
            f"  {p['a']:22} x {p['b']:22} shared={p['shared']:3} "
            f"a_only={len(p['a_only']):3} b_only={len(p['b_only']):3} "
            f"{p['relation']:18} eligible={target}"
        )

    payload = {
        "report": "tool-surface-overlap",
        "method": (
            "exact set arithmetic over tool NAMES returned by a real tools/list "
            "handshake. Name identity does not prove behavioural identity: two "
            "servers can expose browser_click against different browser contexts. "
            "Containment is a NECESSARY condition for retirement, not a sufficient one."
        ),
        "surfaces": {k: len(v) for k, v in sorted(surfaces.items())},
        "pairs": pairs,
    }
    if args.out:
        pathlib.Path(args.out).write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"\nwrote {args.out}")
    print(f"SUCCESS:overlap-report pairs={len(pairs)} surfaces={len(surfaces)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
