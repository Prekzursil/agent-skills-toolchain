"""Structural DAG trace digest. Order, fan-out cardinality, barrier joins only."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def trace_payload(trace: dict[str, Any]) -> dict[str, Any]:
    return {
        "barrier_resolution": trace["barrier_resolution"],
        "fan_out": trace["fan_out"],
        "node_order": trace["node_order"],
    }


def digest_trace(trace: dict[str, Any]) -> str:
    blob = json.dumps(
        trace_payload(trace),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
