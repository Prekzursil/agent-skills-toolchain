"""Structural fingerprint: identity/prose must not leak into the digest."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


_STRUCTURAL = (
    "kind",
    "inputs",
    "outputs",
    "stages",
    "invariants",
    "failure_modes",
    "category",
)


def structural_payload(entry: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in _STRUCTURAL:
        if key in entry:
            payload[key] = entry[key]
    return payload


def fingerprint(entry: Mapping[str, Any]) -> str:
    blob = json.dumps(structural_payload(entry), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
