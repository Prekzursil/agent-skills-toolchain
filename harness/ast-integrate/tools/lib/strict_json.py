"""Strict JSON: duplicate keys are errors, never last-wins."""
from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Sequence


DUPLICATE_KEY_FIXTURE = '{"name":"first","name":"second","keep":true}'


class DuplicateKeyError(ValueError):
    def __init__(self, key: str, first: Any, second: Any) -> None:
        super().__init__(f"duplicate key {key!r}: {first!r} then {second!r}")
        self.key = key
        self.first = first
        self.second = second


def _hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateKeyError(key, out[key], value)
        out[key] = value
    return out


def loads_strict(text: str) -> dict[str, Any]:
    return json.loads(text, object_pairs_hook=_hook)


def dumps_from_pairs(pairs: Sequence[tuple[str, Any]], **kwargs: Any) -> str:
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise DuplicateKeyError(key, seen[key], value)
        seen[key] = value
    return json.dumps(seen, **kwargs)
