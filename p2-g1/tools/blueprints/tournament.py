"""Architecture tournament: dissent is a first-class record."""
from __future__ import annotations

from typing import Any


def finalize_verdict(
    ballots: list[dict[str, Any]],
    minority_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    choices = [str(b.get("choice") or "") for b in ballots]
    unique = {c for c in choices if c}
    winner = max(unique, key=choices.count) if unique else None
    minority = [
        b
        for b in ballots
        if b.get("choice") and str(b.get("choice")) != winner
    ]
    named = [b for b in ballots if b.get("minority_record") or b.get("dissent")]
    if minority_record:
        pos = str(minority_record.get("position") or minority_record.get("choice") or "")
        if pos and pos == winner:
            return {
                "accepted": False,
                "reason": "majority-echo-minority",
                "minority": [],
                "winner": winner,
            }
        named.append(minority_record)
    if len(unique) <= 1 and not named:
        return {
            "accepted": False,
            "reason": "unanimous-without-minority",
            "minority": [],
            "winner": winner,
        }
    if named and len(unique) <= 1:
        return {
            "accepted": True,
            "reason": "unanimous-with-named-minority",
            "minority": named,
            "winner": winner,
        }
    return {
        "accepted": True,
        "reason": "split-ballots",
        "minority": minority or named,
        "winner": winner,
    }
