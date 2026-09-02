"""Token-presence re-identification attack against scripted openings."""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def attack_tokens(persona: Mapping[str, Any]) -> list[str]:
    tokens = [str(t) for t in persona.get("style_tokens") or []]
    tokens.append(str(persona.get("name") or ""))
    tokens.append(f"tool://seat/{persona['id']}/open")
    tokens.append(f"trace:{persona['id']}")
    return [t for t in tokens if t]


def classify(text: str, personas: Sequence[Mapping[str, Any]]) -> str | None:
    scores: dict[str, int] = {}
    for p in personas:
        pid = str(p["id"])
        score = 0
        for tok in attack_tokens(p):
            if tok and tok in text:
                score += 1
        scores[pid] = score
    best = max(scores.values()) if scores else 0
    if best <= 0:
        return None
    winners = [pid for pid, s in scores.items() if s == best]
    if len(winners) != 1:
        return None
    return winners[0]


def accuracy(
    items: Sequence[tuple[str, str]],
    personas: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """items: (text, true_seat_id). Chance = 1/n_seats."""
    n = len(items)
    hits = 0
    identified = 0
    for text, true_id in items:
        pred = classify(text, personas)
        if pred is not None:
            identified += 1
            if pred == true_id:
                hits += 1
    n_seats = max(1, len(personas))
    chance = 1.0 / n_seats
    acc = hits / n if n else 0.0
    # Conservative: unidentified counts as a miss. Above-chance if acc > chance
    # plus a 2.5-sigma binomial margin under H0=chance.
    margin = 2.5 * (chance * (1.0 - chance) / max(n, 1)) ** 0.5 if n else 0.0
    return {
        "n": n,
        "hits": hits,
        "identified": identified,
        "accuracy": acc,
        "chance": chance,
        "margin": margin,
        "above_chance": acc > chance + margin,
        "vacuous": identified == 0 and n > 0,
    }


def plant_traces(
    items: Sequence[tuple[str, str]],
) -> list[tuple[str, str]]:
    return [(text + f" trace:{true_id}", true_id) for text, true_id in items]
