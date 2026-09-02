"""Closed mapper: every free-text string -> one MX-* id or NEW-MECHANISM.

An unmapped string is a vocabulary gap (NEW-MECHANISM), never a
free-text fallback and never a silently invented id.
"""
from __future__ import annotations

import re
from typing import Any

from vocab import GAP, MECHANISMS, alias_index, by_id, vocab_ids

TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "to",
        "and",
        "or",
        "in",
        "on",
        "for",
        "with",
        "by",
        "is",
        "its",
        "that",
        "this",
        "as",
        "be",
        "not",
        "from",
        "must",
        "than",
        "into",
        "over",
        "each",
        "other",
        "one",
        "two",
        "same",
    }
)
SCORE_FLOOR = 0.22
SCORE_MARGIN = 0.04


def normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def tokens(text: str) -> frozenset[str]:
    return frozenset(
        t for t in TOKEN_RE.findall(normalize(text)) if t not in STOP
    )


def _bag(mech: dict[str, Any], *, aliases: bool) -> frozenset[str]:
    parts = [str(mech["definition"]), str(mech["discriminating_example"])]
    if aliases:
        parts.extend(str(a) for a in mech.get("aliases") or ())
    bag = set(tokens(" ".join(parts)))
    bag.update(str(k).lower() for k in mech.get("keys") or ())
    return frozenset(bag)


def score_against(text: str, mech: dict[str, Any], *, aliases: bool) -> float:
    """Overlap + key-hit score. Blind reader must pass aliases=False."""
    text_tok = tokens(text)
    bag = _bag(mech, aliases=aliases)
    if not text_tok or not bag:
        return 0.0
    inter = len(text_tok & bag)
    overlap = inter / min(len(text_tok), len(bag))
    keys = frozenset(str(k).lower() for k in mech.get("keys") or ())
    key_hits = (len(text_tok & keys) / len(keys)) if keys else 0.0
    return 0.55 * overlap + 0.45 * key_hits


def map_one(text: str, *, use_aliases: bool = True) -> dict[str, Any]:
    raw = text if isinstance(text, str) else str(text)
    stripped = raw.strip()
    if not stripped:
        return {
            "source": raw,
            "vocab_id": GAP,
            "rule": "empty-or-missing",
            "gap": True,
            "scores": {},
        }
    key = normalize(stripped)
    aliases = alias_index()
    if use_aliases and key in aliases:
        return {
            "source": stripped,
            "vocab_id": aliases[key],
            "rule": "exact-alias",
            "gap": False,
            "scores": {aliases[key]: 1.0},
        }
    scored = [
        (score_against(stripped, mech, aliases=use_aliases), str(mech["id"]))
        for mech in MECHANISMS
    ]
    scored.sort(reverse=True)
    scores = {mid: round(sc, 4) for sc, mid in scored}
    top_sc, top_id = scored[0]
    second_sc = scored[1][0] if len(scored) > 1 else 0.0
    if top_sc >= SCORE_FLOOR and (top_sc - second_sc) >= SCORE_MARGIN:
        return {
            "source": stripped,
            "vocab_id": top_id,
            "rule": "scored-definition",
            "gap": False,
            "scores": scores,
        }
    return {
        "source": stripped,
        "vocab_id": GAP,
        "rule": "below-floor-or-ambiguous",
        "gap": True,
        "scores": scores,
    }


def map_all(strings: list[str], *, use_aliases: bool = True) -> list[dict[str, Any]]:
    return [map_one(s, use_aliases=use_aliases) for s in strings]


def closed_ids(rows: list[dict[str, Any]]) -> set[str]:
    allowed = set(vocab_ids()) | {GAP}
    return {str(r["vocab_id"]) for r in rows if str(r["vocab_id"]) not in allowed}


def unique_mapping(rows: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Distinct source string -> set of assigned ids (must be size 1)."""
    by_src: dict[str, set[str]] = {}
    for row in rows:
        src = normalize(str(row["source"]))
        by_src.setdefault(src, set()).add(str(row["vocab_id"]))
    return {s: ids for s, ids in by_src.items() if len(ids) != 1}


def fallback_mutant(text: str) -> str:
    """Illegal free-text fallback: returns the source string as the id."""
    return (text or "").strip() or GAP


def invent_id_mutant(text: str) -> str:
    """Illegal open vocabulary: mints an MX id instead of recording a gap."""
    row = map_one(text)
    if row["gap"]:
        return "MX-9001"
    return str(row["vocab_id"])


def definition_of(mid: str) -> str:
    return str(by_id()[mid]["definition"])
