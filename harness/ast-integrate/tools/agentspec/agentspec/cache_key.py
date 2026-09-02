"""Content-addressed cache key derivation (IMP-0229)."""
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


class InvalidCacheKey(ValueError):
    pass


def derive_cache_key(inputs: dict[str, Any], fields: Iterable[str] | None = None) -> str:
    use = list(fields or CACHE_KEY_FIELDS)
    missing = [f for f in use if f not in inputs]
    if missing:
        raise InvalidCacheKey(f"missing fields {missing}")
    payload = {k: inputs[k] for k in use}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
