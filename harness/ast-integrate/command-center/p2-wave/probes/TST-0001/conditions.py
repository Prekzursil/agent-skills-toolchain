#!/usr/bin/env python3
"""Shared condition catalog for TST-0001. No evaluation logic lives here."""
from __future__ import annotations

import json
from typing import Any

CONDITION_IDS = tuple(f"C{i:02d}" for i in range(1, 13))

CONDITION_TEXT = {
    "C01": "process/task reached a valid terminal state",
    "C02": "expected artifact exists",
    "C03": "artifact is non-empty and exceeds a meaningful minimum size",
    "C04": "artifact parses against its schema",
    "C05": "required sentinel is present",
    "C06": "required evidence anchors exist",
    "C07": "required tests ran and passed",
    "C08": "negative controls or mutations fail as expected",
    "C09": "independent reviewer status is PASS",
    "C10": "no unresolved P0/P1 defect is attached",
    "C11": "output was registered in the artifact manifest",
    "C12": "downstream consumers can read it",
}

REASONS = {
    "C01": "state is not a completion terminal (SUCCESS/COMPLETE/PASS/DELIVERED)",
    "C02": "expected artifact does not exist on disk",
    "C03": "artifact is empty or below min_bytes_threshold",
    "C04": "artifact does not parse against its schema",
    "C05": "required sentinel is absent from the artifact",
    "C06": "required evidence anchors are missing",
    "C07": "required tests did not run and pass",
    "C08": "negative controls or mutations did not fail as expected",
    "C09": "independent reviewer status is not PASS",
    "C10": "unresolved P0/P1 defect is attached",
    "C11": "output is not registered in the artifact manifest",
    "C12": "downstream consumers cannot read it",
}

PASS_REASON = "all 12 conditions satisfied"

COMPLETION_STATES = frozenset({"SUCCESS", "COMPLETE", "PASS", "DELIVERED"})
DEFAULT_MIN_BYTES = 200
REQUIRED_SENTINEL = "SUCCESS:CORPUS-PASS"

ARTIFACT_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["unit_id", "state", "sentinel"],
    "properties": {
        "unit_id": {"type": "string", "minLength": 1},
        "state": {"type": "string", "minLength": 1},
        "sentinel": {"type": "string", "minLength": 1},
    },
    "additionalProperties": True,
}


def verdict_obj(verdict: str, failing_condition_id: str | None, reason: str) -> dict:
    return {
        "failing_condition_id": failing_condition_id,
        "reason": reason,
        "verdict": verdict,
    }


def pass_verdict() -> dict:
    return verdict_obj("PASS", None, PASS_REASON)


def fail_verdict(cid: str) -> dict:
    if cid not in REASONS:
        raise KeyError(cid)
    return verdict_obj("FAIL", cid, REASONS[cid])


def dumps_verdict(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


fail_verdict = fail_verdict
pass_verdict = pass_verdict
