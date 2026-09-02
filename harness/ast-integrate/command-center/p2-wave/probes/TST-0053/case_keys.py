"""Case-distinct JSON key collision: detect, refuse to emit, refuse to merge.

The seeded failure class is a case-insensitive consumer downstream of a
case-sensitive producer. RFC 8259 names SHOULD be unique; CPython, Node, and
jq still keep both "Name" and "name". A later casefold index silently drops
one value with no error.

This module is the unit's producer and pipeline reader. Exact duplicate keys
are TST-0054; they are still refused here so last-wins cannot hide a plant.
"""
from __future__ import annotations

import json
from typing import Any

NAME_UPPER_VALUE = "uppercase-N"
NAME_LOWER_VALUE = "lowercase-n"
FIXTURE_ID = "tst-0053-case-collision-fixture"

# Raw bytes of the planted document. Must not go through a Python dict first
# if we ever need exact duplicate keys; Name/name are distinct in a dict.
FIXTURE_TEXT = (
    "{\n"
    f'  "Name": "{NAME_UPPER_VALUE}",\n'
    f'  "name": "{NAME_LOWER_VALUE}",\n'
    f'  "id": "{FIXTURE_ID}",\n'
    '  "version": "1.0.0"\n'
    "}\n"
)

CLEAN_OBJECT: dict[str, Any] = {
    "id": FIXTURE_ID,
    "name": "harness",
    "version": "1.0.0",
}

COLLIDING_OBJECT: dict[str, Any] = {
    "Name": NAME_UPPER_VALUE,
    "name": NAME_LOWER_VALUE,
    "id": FIXTURE_ID,
    "version": "1.0.0",
}


class CaseKeyError(ValueError):
    def __init__(self, classification: str, message: str, keys: list[str] | None = None):
        super().__init__(message)
        self.classification = classification
        self.keys = keys or []


def extract_pairs(text: str) -> list[tuple[str, Any]]:
    """Byte-level object members of the root object (object_pairs_hook)."""
    captured: list[tuple[str, Any]] = []

    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        # Root object is the last hook call for a single-object document.
        captured.clear()
        captured.extend(pairs)
        return dict(pairs)

    json.loads(text, object_pairs_hook=hook)
    return list(captured)


def root_name_pair(text: str) -> dict[str, Any]:
    pairs = extract_pairs(text)
    names = [(k, v) for k, v in pairs if k.casefold() == "name"]
    return {
        "pairs": [{"key": k, "value": v} for k, v in pairs],
        "name_keys": [k for k, _ in names],
        "name_values": [v for _, v in names],
        "both_present": [k for k, _ in names] == ["Name", "name"]
        or {k for k, _ in names} == {"Name", "name"},
        "distinct_values": len({v for _, v in names}) >= 2,
    }


def collisions_in(obj: Any, path: str = "$") -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(obj, dict):
        folded: dict[str, str] = {}
        for key in obj:
            fold = key.casefold()
            prior = folded.get(fold)
            if prior is not None and prior != key:
                found.append(
                    {
                        "path": path,
                        "keys": [prior, key],
                        "fold": fold,
                    }
                )
            else:
                folded[fold] = key
        for key, value in obj.items():
            child = f"{path}.{key}" if path != "$" else f"$.{key}"
            found.extend(collisions_in(value, child))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            found.extend(collisions_in(value, f"{path}[{i}]"))
    return found


def _pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    folded: dict[str, str] = {}
    for key, value in pairs:
        if key in seen:
            raise CaseKeyError(
                "duplicate-key",
                f"duplicate key {key!r} refused (not last-wins overwrite)",
                [key],
            )
        seen[key] = value
        fold = key.casefold()
        prior = folded.get(fold)
        if prior is not None and prior != key:
            raise CaseKeyError(
                "case-collision",
                (
                    "case-distinct keys "
                    f"{prior!r} and {key!r} collide under a case-insensitive client"
                ),
                [prior, key],
            )
        folded[fold] = key
    return seen


def pipeline_loads(text: str) -> Any:
    """Unit pipeline reader: case-distinct keys error; they do not merge."""
    try:
        return json.loads(text, object_pairs_hook=_pairs_hook)
    except CaseKeyError:
        raise
    except json.JSONDecodeError as exc:
        raise CaseKeyError("schema-invalid", f"JSONDecodeError: {exc}") from exc


def pipeline_read_path(path: Any) -> Any:
    return pipeline_loads(path.read_text(encoding="utf-8"))


def naive_dumps(obj: Any) -> str:
    """Case-sensitive producer that will emit colliding keys. Known-broken."""
    return json.dumps(obj, indent=2, ensure_ascii=True) + "\n"


def emit_json(obj: Any) -> str:
    """Producer: refuse before dumps if any object has case-colliding keys."""
    found = collisions_in(obj)
    if found:
        keys = found[0]["keys"]
        raise CaseKeyError(
            "case-collision",
            (
                "producer refuses to emit case-colliding keys "
                f"{keys[0]!r} and {keys[1]!r} at {found[0]['path']}"
            ),
            list(keys),
        )
    return naive_dumps(obj)


def emit_first_mutant(obj: Any) -> dict[str, Any]:
    """Known-broken: dumps first, then notices the collision. Detector control."""
    text = naive_dumps(obj)
    found = collisions_in(obj)
    if found:
        keys = found[0]["keys"]
        err = CaseKeyError(
            "case-collision",
            (
                "producer refuses to emit case-colliding keys "
                f"{keys[0]!r} and {keys[1]!r} at {found[0]['path']}"
            ),
            list(keys),
        )
        return {
            "status": "refused-after-emit",
            "text": text,
            "error": str(err),
            "emitted_colliding_bytes": True,
            "contains_Name": '"Name"' in text,
            "contains_name": '"name"' in text,
        }
    return {
        "status": "emitted",
        "text": text,
        "error": None,
        "emitted_colliding_bytes": False,
        "contains_Name": '"Name"' in text,
        "contains_name": '"name"' in text,
    }
