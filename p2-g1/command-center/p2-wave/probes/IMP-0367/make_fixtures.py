#!/usr/bin/env python3
"""Generate the IMP-0367 question fixtures deterministically (no hand-typed arrays)."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent / "fixtures"


def write(name: str, doc: dict) -> None:
    p = HERE / f"{name}.json"
    p.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print("wrote", p)


def main() -> int:
    n_max = 12

    # Evidence-decisive: unanimous at every N -> N* = 1.
    ev_votes = {}
    for n in range(1, n_max + 1):
        row = ["REJECT"]
        for i in range(2, n + 1):
            row.append("ACCEPT" if i % 4 == 0 else "REJECT")
        ev_votes[str(n)] = row
    ev = {"id": "Q-evidence-decisive", "kind": "evidence-decisive",
          "default_n": 5,
          "note": "majority REJECT at every N (evidence carries it); "
                  "only the N-modulated aggregator moves it",
          "votes_by_n": ev_votes}
    write("evidence-decisive", ev)

    # N-sensitive: majority REJECT below 7, ACCEPT from 7 on.
    nsens = {"id": "Q-alternating", "kind": "alternating", "default_n": 5,
             "note": "answer depends on N: flips until N=7 then stabilises ACCEPT",
             "votes_by_n": {}}
    for n in range(1, n_max + 1):
        if n < 7:
            yes = (n - 1) // 2
            row = ["ACCEPT"] * yes + ["REJECT"] * (n - yes)
        else:
            yes = n - 2
            row = ["REJECT"] * 2 + ["ACCEPT"] * (n - 2)
        nsens["votes_by_n"][str(n)] = row
    write("n-sensitive", nsens)

    # Default-below: REJECT from N=5 on, but ACCEPT at N=1..4 (default 3).
    below = {"id": "Q-default-below", "kind": "default-below", "default_n": 3,
             "note": "default N=3 sits below N*=5 and would emit the wrong answer",
             "votes_by_n": {}}
    for n in range(1, n_max + 1):
        if n < 5:
            row = ["ACCEPT"] * n
        else:
            row = ["REJECT"] * n
        below["votes_by_n"][str(n)] = row
    write("default-below", below)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
