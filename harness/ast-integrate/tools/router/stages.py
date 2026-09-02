"""The two matcher stages fusion consumes, pinned so their output is reproducible.

* deterministic stage: :func:`deterministic_score` - the fraction of a query's
  structured role fields (keyword / path / cwd / tool_verb) that a capability's
  trigger rows fire on.  No model, no free text.
* semantic stage: :func:`semantic_score` - character-trigram cosine between
  query text and capability description (``SEMANTIC_METHOD``).  An offline
  stand-in for the neural embedding stage; ``semantic_method_digest`` pins the
  exact method text so a receipt can say which stand-in produced its rank list.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Any, Iterable

__all__ = [
    "SEMANTIC_METHOD",
    "SEMANTIC_METHOD_SPEC",
    "char_trigrams",
    "cosine",
    "deterministic_score",
    "semantic_method_digest",
    "semantic_score",
]

SEMANTIC_METHOD = "char-trigram-cosine-v1"
SEMANTIC_METHOD_SPEC = (
    "lower-case; collapse runs of non-alphanumerics to one space; pad with one "
    "space each side; count overlapping character trigrams; cosine similarity of "
    "the two count vectors; 0.0 when either side has no trigram"
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
ROLE_FIELDS: tuple[str, ...] = ("keyword", "path", "cwd", "tool_verb")


def semantic_method_digest() -> str:
    """sha256 over the method name and its spec text: the stand-in's identity."""
    return hashlib.sha256(f"{SEMANTIC_METHOD}\n{SEMANTIC_METHOD_SPEC}\n".encode("utf-8")).hexdigest()


def char_trigrams(text: str) -> Counter[str]:
    norm = " " + _NON_ALNUM.sub(" ", str(text or "").lower()).strip() + " "
    if len(norm) < 3:
        return Counter()
    return Counter(norm[i : i + 3] for i in range(len(norm) - 2))


def cosine(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b[k] for k, v in a.items() if k in b)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


def semantic_score(query_text: str, description: str) -> float:
    return cosine(char_trigrams(query_text), char_trigrams(description))


def deterministic_score(query: dict[str, Any], triggers: Iterable[dict[str, Any]]) -> float:
    """Fraction of the query's set role fields that some trigger row fires on.

    A trigger row is ``{"kind": <role field>, "pattern": <literal>}``; it fires
    when the query's role value equals the pattern (paths and cwds compare on
    their normalised prefix).  Free-text payload is never read.
    """
    set_roles = [r for r in ROLE_FIELDS if str(query.get(r) or "").strip()]
    if not set_roles:
        return 0.0
    fired = 0
    for role in set_roles:
        value = str(query.get(role)).strip().replace("\\", "/").rstrip("/")
        for row in triggers:
            if str(row.get("kind")) != role:
                continue
            pattern = str(row.get("pattern") or "").replace("\\", "/").rstrip("/")
            if not pattern:
                continue
            if role in {"path", "cwd"}:
                hit = value == pattern or value.startswith(pattern + "/")
            elif role == "keyword":
                hit = value.lower() == pattern.lower()
            else:
                hit = value == pattern
            if hit:
                fired += 1
                break
    return fired / len(set_roles)
