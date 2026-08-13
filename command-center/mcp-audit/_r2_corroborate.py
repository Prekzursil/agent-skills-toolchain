#!/usr/bin/env python3
"""Corroborate the round-1 measurements against the independent round-2 sweep.

The round-2 sweep exists because the producer had to be fixed (``rss_bytes``), but it is
also a mechanically independent re-measurement of every tool surface a day later, on a
differently-loaded box.  A second run that agrees is corroboration; one that disagrees
would retire the round-1 numbers.  Either way it must be reported, not assumed.

Compares, per server: ``tool_count`` and the exact set of tool NAMES.  Names matter more
than the count -- two runs can agree on 24 while advertising different tools, which would
silently invalidate the overlap arithmetic that produced the single DISABLE.

Run: ``python _r2_corroborate.py`` -> exit 0 / 1.
"""

from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def load(path: pathlib.Path) -> dict[str, dict]:
    blob = json.loads(path.read_text(encoding="utf-8"))
    return {r["name"]: r for r in blob["rows"] if r.get("call_verified")}


def compare(r1: dict[str, dict], r2: dict[str, dict], common: list[str]) -> list[str]:
    """Return the disagreements between two runs, by count and then by name set."""
    disagree: list[str] = []
    for name in common:
        a, b = r1[name], r2[name]
        if a["tool_count"] != b["tool_count"]:
            disagree.append(f"{name}: count {a['tool_count']} vs {b['tool_count']}")
            continue
        na, nb = set(a.get("tool_names") or []), set(b.get("tool_names") or [])
        if na != nb:
            disagree.append(
                f"{name}: same count but name sets differ "
                f"(+{sorted(nb - na)[:3]} -{sorted(na - nb)[:3]})"
            )
    return disagree


def control(r1: dict[str, dict], r2: dict[str, dict], common: list[str]) -> bool:
    """Prove the comparison is not vacuous, in the one way that matters.

    Two runs whose ``tool_names`` were both MISSING would compare equal (empty == empty)
    and this script would print a confident agreement while measuring nothing -- the
    control-that-cannot-distinguish failure.  So: require the name sets to be non-empty,
    then rename one tool in one run and require a disagreement to be reported.
    """
    populated = [n for n in common if r2[n].get("tool_names")]
    if len(populated) != len(common):
        print(f"  CONTROL FAILED: {len(common) - len(populated)} rows carry no names")
        return False
    victim = populated[0]
    mutated = {k: dict(v) for k, v in r2.items()}
    names = list(mutated[victim]["tool_names"])
    names[0] = names[0] + "_MUTANT"
    mutated[victim]["tool_names"] = names
    fired = bool(compare(r1, mutated, common))
    print(
        f"  control: all {len(common)} rows carry names; renamed one tool in "
        f"{victim!r} -> disagreement reported? {fired}"
    )
    return fired


def main() -> int:
    r1 = load(HERE / "capability-matrix.json")
    r2 = load(HERE / "capability-matrix-r2.json")
    common = sorted(set(r1) & set(r2))
    if not common:
        print("FAILED:r2-corroborate no overlapping verified rows (fail closed)")
        return 1

    disagree = compare(r1, r2, common)
    print(f"== corroboration over {len(common)} verified servers ==")
    if not control(r1, r2, common):
        print("FAILED:r2-corroborate the comparison cannot detect a difference")
        return 1
    for name in common:
        print(
            f"  {name:22} r1={r1[name]['tool_count']:>4} r2={r2[name]['tool_count']:>4}"
        )
    only1 = sorted(set(r1) - set(r2))
    only2 = sorted(set(r2) - set(r1))
    if only1:
        print(f"  verified in r1 only: {only1}")
    if only2:
        print(f"  verified in r2 only: {only2}")
    if disagree:
        print("DISAGREEMENTS:")
        for d in disagree:
            print(f"  {d}")
        print(f"FAILED:r2-corroborate {len(disagree)} server(s) disagree")
        return 1
    print(
        f"SUCCESS:r2-corroborate {len(common)}/{len(common)} agree on count AND names"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
