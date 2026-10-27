"""Case-collision producer/reader for TST-0053 (rebuild, shard21-w2).

emit(): the producer. Refuses to emit a document whose object keys collide
case-insensitively ("Name" vs "name") - the silent-merge defect this unit
exists for. Emitting distinct keys is fine.

load_ci(): the case-insensitive DOWNSTREAM reader. Demonstrates the silent
data-loss path: feeding it a case-colliding document keeps only the last
member per case-folded key, so "Name" is silently lost.
"""
from __future__ import annotations

import json
from typing import Any


class CaseCollisionError(ValueError):
    """Raised when a document's object keys collide case-insensitively."""


def _iter_pairs(node: Any, pairs: list) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            pairs.append(str(k))
            _iter_pairs(v, pairs)
    elif isinstance(node, list):
        for item in node:
            _iter_pairs(item, pairs)


def case_collisions(doc: Any) -> dict[str, list[str]]:
    """Map case-folded key -> the distinct literal keys that collide on it."""
    by_fold: dict[str, list[str]] = {}
    pairs: list[str] = []
    _iter_pairs(doc, pairs)
    for k in pairs:
        by_fold.setdefault(k.casefold(), []).append(k)
    return {f: ks for f, ks in by_fold.items() if len(set(ks)) > 1}


def emit(doc: dict) -> bytes:
    """Producer: refuses case-colliding key sets, emits clean documents."""
    bad = case_collisions(doc)
    if bad:
        raise CaseCollisionError(
            "case-colliding keys " + repr(bad) + "; case-insensitive downstream readers would silently drop one"
        )
    return json.dumps(doc, indent=1).encode("utf-8")


def load_ci(raw: bytes) -> dict:
    """The silent-merge path: a case-insensitive reader keeps the LAST member
    per case-folded key, dropping the rest without error."""
    doc = json.loads(raw.decode("utf-8"))
    out: dict = {}
    def merge(node):
        if isinstance(node, dict):
            for k, v in node.items():
                out[k.casefold()] = v
        return out
    merge(doc)
    return out
