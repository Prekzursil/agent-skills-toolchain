"""Research search/fetch cache key (RES-0171).

Identity fields required by the unit question, plus source_class and
kind so a per-class TTL cannot be applied to the wrong entry.

Encoding is clock-free: wall time enters only as the already-discretized
time_bucket string supplied by policy.time_bucket().
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

KEY_FIELDS = (
    "query",
    "backend",
    "filters",
    "time_bucket",
    "backend_version",
    "source_class",
    "kind",
)

REQUIRED_QUESTION_FIELDS = (
    "query",
    "backend",
    "filters",
    "time_bucket",
    "backend_version",
)

ALLOWED_KINDS = frozenset({"search", "fetch"})


class InvalidResearchCacheKey(ValueError):
    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"invalid research cache key field {field}: {reason}")


def _canonical_dumps(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _require_text(field: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidResearchCacheKey(field, "missing-or-blank")
    return value


def _require_filters(value: Any) -> Any:
    if value is None:
        raise InvalidResearchCacheKey("filters", "missing")
    if isinstance(value, (str, int, bool, list, dict)):
        return value
    raise InvalidResearchCacheKey("filters", f"unsupported-type:{type(value).__name__}")


def normalize_inputs(inputs: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(inputs, Mapping):
        raise InvalidResearchCacheKey("<root>", "not-a-mapping")
    missing = [f for f in KEY_FIELDS if f not in inputs]
    if missing:
        raise InvalidResearchCacheKey(missing[0], "absent")
    kind = _require_text("kind", inputs["kind"])
    if kind not in ALLOWED_KINDS:
        raise InvalidResearchCacheKey("kind", f"not-in:{sorted(ALLOWED_KINDS)}")
    return {
        "query": _require_text("query", inputs["query"]),
        "backend": _require_text("backend", inputs["backend"]),
        "filters": _require_filters(inputs["filters"]),
        "time_bucket": _require_text("time_bucket", inputs["time_bucket"]),
        "backend_version": _require_text("backend_version", inputs["backend_version"]),
        "source_class": _require_text("source_class", inputs["source_class"]),
        "kind": kind,
    }


def derive_cache_key(inputs: Mapping[str, Any]) -> str:
    """Stable SHA-256 hex of the canonical seven-field record."""
    record = normalize_inputs(inputs)
    return hashlib.sha256(_canonical_dumps(record).encode("utf-8")).hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
