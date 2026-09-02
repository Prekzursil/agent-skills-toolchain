"""Naive reporter that turns `grep -c pat || echo 0` into two claims.

Measured pathology: grep -c prints 0 and exits 1 on no match, so
`grep -c pat || echo 0` prints `0\\n0`. A reporter that treats the captured
string `!= "0"` as "all N PRs hit" AND treats a `0` line as "empty
intersection" publishes both at once.
"""
from __future__ import annotations

from invariants import ALL_HIT, EMPTY_INTERSECTION, RunOutput

UNIVERSE = 7


def naive_from_grep_c_blob(raw: str, universe: int = UNIVERSE) -> RunOutput:
    stripped = raw.strip("\n")
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip() != ""]
    claims: set[str] = set()
    # The tell: "0\\n0" is not equal to "0", so this branch fires on the blob.
    if stripped != "0":
        claims.add(ALL_HIT)
    if "0" in lines:
        claims.add(EMPTY_INTERSECTION)
    all_hit = ALL_HIT in claims
    empty = EMPTY_INTERSECTION in claims
    return RunOutput(
        counts={
            "universe": universe,
            "hit": universe if all_hit else 0,
            "miss": 0 if all_hit else universe,
            "intersection": 0 if empty else universe,
        },
        claims=claims,
        raw=raw,
        n_universe=universe,
    )
