"""Declared CNL-0119 ballot profiles (one shared ranking per voter).

Cardinal methods (approval_top2, score_5310, borda) project the same ranking;
they do not receive a second ballot.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
PROFILES_PATH = FIXTURES / "profiles.json"

# (ranking, multiplicity) — expanded to one ballot per voter in dump order.
RAW: list[dict] = [
    {
        "id": "unanimous-3",
        "role": "negative-control-agree",
        "candidates": ["A", "B", "C"],
        "packs": [(["A", "B", "C"], 7)],
    },
    {
        "id": "majority-clear",
        "role": "agree-majority",
        "candidates": ["A", "B", "C"],
        "packs": [(["A", "B", "C"], 5), (["B", "A", "C"], 2)],
    },
    {
        "id": "spoiler-triple",
        "role": "planted-disagreement",
        "candidates": ["A", "B", "C"],
        "packs": [
            (["A", "B", "C"], 6),
            (["C", "B", "A"], 5),
            (["B", "C", "A"], 2),
        ],
    },
    {
        "id": "center-squeeze",
        "role": "disagreement",
        "candidates": ["A", "B", "C"],
        "packs": [
            (["A", "B", "C"], 5),
            (["C", "B", "A"], 4),
            (["B", "A", "C"], 2),
        ],
    },
    {
        "id": "approval-split",
        "role": "disagreement",
        "candidates": ["A", "B", "C"],
        "packs": [
            (["A", "B", "C"], 4),
            (["B", "C", "A"], 3),
            (["C", "A", "B"], 2),
        ],
    },
    {
        "id": "close-plurality",
        "role": "sensitivity",
        "candidates": ["A", "B", "C"],
        "packs": [(["A", "B", "C"], 4), (["B", "A", "C"], 3)],
    },
    {
        "id": "cycle-asymmetric",
        "role": "cycle",
        "candidates": ["A", "B", "C"],
        "packs": [
            (["A", "B", "C"], 4),
            (["B", "C", "A"], 3),
            (["C", "A", "B"], 2),
        ],
    },
    {
        "id": "unanimous-4",
        "role": "negative-control-agree",
        "candidates": ["A", "B", "C", "D"],
        "packs": [(["A", "B", "C", "D"], 5)],
    },
    {
        "id": "score-borda-split",
        "role": "ordinal-cardinal",
        "candidates": ["A", "B", "C", "D"],
        "packs": [
            (["A", "C", "B", "D"], 5),
            (["B", "D", "C", "A"], 5),
            (["A", "D", "C", "B"], 1),
        ],
    },
]


def expand(raw: dict) -> dict:
    ballots = []
    n = 0
    for ranking, k in raw["packs"]:
        for _ in range(int(k)):
            ballots.append({"voter": f"v{n:02d}", "ranking": list(ranking)})
            n += 1
    if n % 2 == 0:
        raise SystemExit(f"even voter count on {raw['id']} (pairwise ties)")
    return {
        "id": raw["id"],
        "role": raw["role"],
        "candidates": list(raw["candidates"]),
        "n_ballots": n,
        "ballots": ballots,
    }


def profiles() -> list[dict]:
    return [expand(r) for r in RAW]


def dump() -> Path:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    doc = {
        "unit_id": "CNL-0119",
        "note": (
            "One ranking per voter. Approval/score/Borda/IRV/plurality/"
            "Copeland all read this ranking; there is no second ballot type."
        ),
        "profiles": profiles(),
    }
    PROFILES_PATH.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return PROFILES_PATH


def load() -> list[dict]:
    if not PROFILES_PATH.is_file():
        dump()
    doc = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    return list(doc["profiles"])


if __name__ == "__main__":
    p = dump()
    print(f"wrote {p} n_profiles={len(profiles())}")
