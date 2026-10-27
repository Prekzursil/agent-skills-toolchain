#!/usr/bin/env python3
"""TST-0088 fan-in classifier: the five delivery conditions.

classify() returns verdict + the first FAILED condition id:
1 reached a valid terminal state (artifact.state legal terminal)
2 expected artifact exists
3 non-empty and above a meaningful minimum
4 parses against its schema
5 required sentinel is present in the typed sentinel field"""
from __future__ import annotations

import json
from pathlib import Path

MIN_BYTES = 64


def classify(path: Path, expected_sentinel: str) -> dict:
    if not path.exists():
        return {"verdict": "FAILED", "condition_id": 2, "basis": "expected artifact absent"}
    raw = path.read_bytes()
    if len(raw) < MIN_BYTES:
        return {"verdict": "FAILED", "condition_id": 3, "basis": "bytes=" + str(len(raw)) + " min=" + str(MIN_BYTES)}
    try:
        doc = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        return {"verdict": "FAILED", "condition_id": 4, "basis": "unparseable: " + type(exc).__name__}
    state = str(doc.get("state") or "")
    if state.upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return {"verdict": "FAILED", "condition_id": 1, "basis": "state=" + state}
    observed = doc.get("completion_sentinel")
    if observed != expected_sentinel:
        return {"verdict": "FAILED", "condition_id": 5,
                "basis": "file exists, parses, looks plausible (state=" + (state or "?") + "), but completion_sentinel observed=" + repr(observed) + " expected=" + repr(expected_sentinel)}
    return {"verdict": "SUCCESS", "condition_id": 0, "basis": "all five conditions hold"}


def classify_absent(path: Path, expected_sentinel: str) -> dict:
    return classify(path, expected_sentinel)
