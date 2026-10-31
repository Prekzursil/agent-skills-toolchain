"""Labelled 50-pair strategic-vote corpus (IMP-0347)."""
from __future__ import annotations

from typing import Any


def _pair(pid: str, label: str, ballot: str, texts: list[str]) -> dict[str, Any]:
    hist = [{"t": i + 1, "text": t} for i, t in enumerate(texts)]
    return {
        "id": pid,
        "label": label,
        "ballot": ballot,
        "reasoning_history": hist,
        "participant_id": pid,
    }


def labelled_corpus() -> dict[str, Any]:
    pairs = []
    for i in range(20):
        pairs.append(_pair(f"SV-{i:02d}", "strategic_vote", "nay", [f"I support this. STANCE:AYE filler {i}"]))
    for i in range(10):
        pairs.append(
            _pair(
                f"CM-{i:02d}",
                "change_of_mind",
                "nay",
                [
                    f"Initially I was for it. STANCE:AYE {i}",
                    f"Updated: evidence reversed me. STANCE:NAY {i}",
                ],
            )
        )
    for i in range(20):
        pairs.append(_pair(f"OK-{i:02d}", "sincere", "aye", [f"I am for it. STANCE:AYE {i}"]))
    counts: dict[str, int] = {}
    for p in pairs:
        counts[p["label"]] = counts.get(p["label"], 0) + 1
    return {
        "n_pairs": len(pairs),
        "pairs": pairs,
        "label_counts": counts,
        "profiles": [],
    }
