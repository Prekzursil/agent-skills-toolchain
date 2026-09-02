"""Deterministic on-disk postcondition oracle (packaged-artifact-smoke pattern).

Verdict is a pure function of artifact bytes + family spec: exists, min size,
UTF-8 JSON object, family/case identity, then family-specific field checks.
No network, no clock, no RNG.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from families import MIN_BYTES, by_id

SENTINEL_MARK = "WFA-0112-ORACLE-V1"


def _get(doc: Any, dotted: str) -> Any:
    cur: Any = doc
    for part in dotted.split("."):
        if cur is None:
            return None
        if part.isdigit():
            if not isinstance(cur, list):
                return None
            idx = int(part)
            if idx < 0 or idx >= len(cur):
                return None
            cur = cur[idx]
            continue
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _run_check(doc: dict[str, Any], check: tuple[Any, ...]) -> str | None:
    path = str(check[0])
    op = str(check[1])
    val = _get(doc, path)
    extra = check[2] if len(check) > 2 else None
    if op == "eq":
        return None if val == extra else f"{path}:eq"
    if op == "nonempty_str":
        return None if isinstance(val, str) and val.strip() else f"{path}:nonempty_str"
    if op == "nonempty_list":
        return None if isinstance(val, list) and len(val) > 0 else f"{path}:nonempty_list"
    if op == "min_len":
        n = int(extra)
        return None if isinstance(val, str) and len(val) >= n else f"{path}:min_len"
    if op == "gte":
        n = int(extra)
        return None if isinstance(val, (int, float)) and not isinstance(val, bool) and val >= n else f"{path}:gte"
    if op == "is_true":
        return None if val is True else f"{path}:is_true"
    if op == "is_false":
        return None if val is False else f"{path}:is_false"
    if op == "is_null":
        return None if val is None and path in _present_path(doc, path) else f"{path}:is_null"
    if op == "in_set":
        allowed = extra
        return None if val in allowed else f"{path}:in_set"
    return f"{path}:unknown-op"


def _present_path(doc: dict[str, Any], dotted: str) -> set[str]:
    """Return {dotted} if the last key exists even when its value is null."""
    parts = dotted.split(".")
    cur: Any = doc
    for i, part in enumerate(parts):
        if part.isdigit():
            if not isinstance(cur, list):
                return set()
            idx = int(part)
            if idx < 0 or idx >= len(cur):
                return set()
            cur = cur[idx]
            continue
        if not isinstance(cur, dict) or part not in cur:
            return set()
        if i == len(parts) - 1:
            return {dotted}
        cur = cur[part]
    return {dotted}


def evaluate(path: Path, family_id: str, case_id: str) -> dict[str, Any]:
    spec = by_id(family_id)
    reasons: list[str] = []
    if not path.is_file():
        return {
            "accept": False,
            "reasons": ["missing-file"],
            "family_id": family_id,
            "case_id": case_id,
            "oracle": SENTINEL_MARK,
        }
    raw = path.read_bytes()
    if len(raw) < MIN_BYTES:
        reasons.append("too-small")
    try:
        text = raw.decode("utf-8")
        doc = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        reasons.append("unparseable")
        return {
            "accept": False,
            "reasons": reasons,
            "family_id": family_id,
            "case_id": case_id,
            "oracle": SENTINEL_MARK,
        }
    if not isinstance(doc, dict):
        reasons.append("not-object")
        return {
            "accept": False,
            "reasons": reasons,
            "family_id": family_id,
            "case_id": case_id,
            "oracle": SENTINEL_MARK,
        }
    if doc.get("family_id") != family_id:
        reasons.append("family-mismatch")
    if doc.get("case_id") != case_id:
        reasons.append("case-mismatch")
    if doc.get("network_used") is not False:
        reasons.append("network-flag")
    if doc.get("oracle_kind") != "on-disk-postcondition":
        reasons.append("oracle-kind")
    for check in spec["checks"]:
        hit = _run_check(doc, tuple(check))
        if hit:
            reasons.append(hit)
    reasons = list(dict.fromkeys(reasons))
    return {
        "accept": len(reasons) == 0,
        "reasons": reasons,
        "family_id": family_id,
        "case_id": case_id,
        "oracle": SENTINEL_MARK,
        "bytes": len(raw),
    }


def evaluate_twice(path: Path, family_id: str, case_id: str) -> dict[str, Any]:
    a = evaluate(path, family_id, case_id)
    b = evaluate(path, family_id, case_id)
    return {
        "identical": a == b,
        "first": a,
        "second": b,
    }
