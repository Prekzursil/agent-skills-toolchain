"""Strict artifact parse cache: truncated/unparseable bytes must not cache.

Downstream consumers read only what the cache actually holds. A parse
failure records byte_offset + kind and leaves has(id) False.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore[assignment]


class ParseFailure(ValueError):
    def __init__(self, *, kind: str, byte_offset: int, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.byte_offset = byte_offset
        self.message = message

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "byte_offset": self.byte_offset,
            "message": self.message,
        }


@dataclass
class _Entry:
    value: dict[str, Any]
    raw: bytes


class ArtifactParseCache:
    def __init__(self) -> None:
        self._ok: dict[str, _Entry] = {}
        self._fail: dict[str, ParseFailure] = {}

    def parse(self, artifact_id: str, raw: bytes | str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
        if isinstance(raw, str):
            text = raw
            raw_bytes = raw.encode("utf-8")
        else:
            raw_bytes = raw
            text = raw.decode("utf-8")
        raw = raw_bytes
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            fail = ParseFailure(
                kind="json-decode",
                byte_offset=int(exc.pos or 0),
                message=str(exc),
            )
            self._fail[artifact_id] = fail
            self._ok.pop(artifact_id, None)
            raise fail from exc
        if not isinstance(obj, dict):
            fail = ParseFailure(
                kind="json-decode",
                byte_offset=0,
                message="artifact JSON must be an object",
            )
            self._fail[artifact_id] = fail
            self._ok.pop(artifact_id, None)
            raise fail
        if schema is not None and jsonschema is not None:
            try:
                jsonschema.Draft7Validator(schema).validate(obj)
            except jsonschema.ValidationError as exc:
                fail = ParseFailure(
                    kind="schema",
                    byte_offset=0,
                    message=exc.message,
                )
                self._fail[artifact_id] = fail
                self._ok.pop(artifact_id, None)
                raise fail from exc
        self._ok[artifact_id] = _Entry(value=obj, raw=raw)
        self._fail.pop(artifact_id, None)
        return obj

    def has(self, artifact_id: str) -> bool:
        return artifact_id in self._ok

    def get(self, artifact_id: str) -> dict[str, Any] | None:
        entry = self._ok.get(artifact_id)
        return entry.value if entry is not None else None

    def inspect(self, artifact_id: str) -> dict[str, Any]:
        if artifact_id in self._ok:
            return {"present": True, "value": self._ok[artifact_id].value}
        return {"present": False, "value": None}


class DownstreamConsumer:
    """Reads only cached successful parses — never the raw truncated bytes."""

    def __init__(self, cache: ArtifactParseCache) -> None:
        self._cache = cache
        self._held: set[str] = set()

    def ingest(self, artifact_id: str) -> bool:
        if self._cache.has(artifact_id):
            self._held.add(artifact_id)
            return True
        self._held.discard(artifact_id)
        return False

    def holds(self, artifact_id: str) -> bool:
        return artifact_id in self._held and self._cache.has(artifact_id)
