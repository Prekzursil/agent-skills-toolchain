"""Content-addressed cache key derivation (IMP-0229).

The key is the SHA-256 of a canonical JSON encoding of exactly the seven
IMP-0141 inputs. Every field is validated before hashing so a blank or
mis-typed input names its field and reason through :class:`InvalidCacheKey`
instead of silently producing a key that collides with a neighbour's.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

CACHE_KEY_FIELDS = (
    "workflow_id",
    "spec_version",
    "unit_id",
    "resolved_prompt",
    "param_values",
    "tool_policy",
    "input_artifact_hashes",
)

_STRING_FIELDS = frozenset({"workflow_id", "spec_version", "unit_id", "resolved_prompt"})
_OBJECT_FIELDS = frozenset({"param_values", "tool_policy"})
_HASH_LIST_FIELDS = frozenset({"input_artifact_hashes"})
_HEX = frozenset("0123456789abcdef")


class InvalidCacheKey(ValueError):
    """A cache-key input is missing, blank or of the wrong shape.

    ``field`` names the offending input and ``reason`` says what was wrong, so a
    caller can report the defect without parsing the message.
    """

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"{field}: {reason}")


def _is_sha256_hex(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= _HEX


def validate_cache_key_inputs(inputs: dict[str, Any], fields: Iterable[str] | None = None) -> dict[str, Any]:
    """Return the validated payload for ``fields`` or raise :class:`InvalidCacheKey`."""
    if not isinstance(inputs, dict):
        raise InvalidCacheKey("inputs", "must be an object")
    use = list(fields or CACHE_KEY_FIELDS)
    payload: dict[str, Any] = {}
    for name in use:
        if name not in inputs:
            raise InvalidCacheKey(name, "missing")
        value = inputs[name]
        if name in _STRING_FIELDS:
            if not isinstance(value, str):
                raise InvalidCacheKey(name, f"must be a string, got {type(value).__name__}")
            if not value.strip():
                raise InvalidCacheKey(name, "blank")
        elif name in _OBJECT_FIELDS:
            if not isinstance(value, dict):
                raise InvalidCacheKey(name, f"must be an object, got {type(value).__name__}")
        elif name in _HASH_LIST_FIELDS:
            if not isinstance(value, (list, tuple)):
                raise InvalidCacheKey(name, f"must be a list, got {type(value).__name__}")
            for i, digest in enumerate(value):
                if not _is_sha256_hex(digest):
                    raise InvalidCacheKey(name, f"entry {i} is not a sha256 hex digest")
        try:
            json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise InvalidCacheKey(name, f"not JSON-encodable: {exc}") from exc
        payload[name] = value
    return payload


def canonical_key_bytes(inputs: dict[str, Any], fields: Iterable[str] | None = None) -> bytes:
    """Canonical (sorted, compact, ASCII) JSON bytes the key is hashed over."""
    payload = validate_cache_key_inputs(inputs, fields)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def derive_cache_key(inputs: dict[str, Any], fields: Iterable[str] | None = None) -> str:
    return hashlib.sha256(canonical_key_bytes(inputs, fields)).hexdigest()
