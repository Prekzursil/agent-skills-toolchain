"""Typed-goal parser (IMP-0193)."""
from __future__ import annotations


def parse_typed_goal(text: str, goal_id: str | None = None) -> dict:
    return {
        "text": text,
        "id": goal_id or "goal.anonymous",
        "tokens": [t.lower() for t in text.replace("/", " ").split() if t],
    }


__all__ = ["parse_typed_goal"]
