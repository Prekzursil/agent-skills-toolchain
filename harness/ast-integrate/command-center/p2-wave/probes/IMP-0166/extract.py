#!/usr/bin/env python3
"""Extract a candidate stop rule into a typed predicate tree.

Inexpressible prose is UNKNOWN-NEEDS-PROBE, never snapped to a nearby metric.
A documented wrapper ('stop when', 'stop if') is stripped; the remainder must
still parse. 'stop when it feels done' therefore stays UNKNOWN-NEEDS-PROBE.
"""
from __future__ import annotations

import re
from typing import Any

from algebra import ParseError, parse, tree_to_dict

CLASS_EVALUABLE = "EVALUABLE"
CLASS_UNKNOWN = "UNKNOWN-NEEDS-PROBE"
CLASS_NONE = "NONE"

_WRAPPER = re.compile(
    r"^(?:stop(?:ping)?(?:\s+rule)?(?:\s+(?:when|if|once|after))?|"
    r"halt(?:\s+when)?|until)\s*[:\-]?\s+",
    re.IGNORECASE,
)


def normalize_source(text: str) -> str:
    raw = text.strip()
    prev = None
    while prev != raw:
        prev = raw
        raw = _WRAPPER.sub("", raw).strip()
    return raw


def extract_stop_rule(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return a classification row. Never approximates an unparseable remainder."""
    cid = str(candidate.get("id") or "")
    src = candidate.get("stop")
    if src is None:
        src = candidate.get("stop_rule")
    if src is None:
        src = candidate.get("stopping_expression")
    if src is None or (isinstance(src, str) and not src.strip()):
        return {
            "id": cid,
            "classification": CLASS_NONE,
            "source": src if isinstance(src, str) else "",
            "normalized": "",
            "tree": None,
            "reason": "no-stop-rule",
        }
    if isinstance(src, dict):
        kind = src.get("kind")
        if kind in {"CMP", "ALL", "ANY", "NOT", "WEIGHTED", "ATOM"}:
            return {
                "id": cid,
                "classification": CLASS_EVALUABLE,
                "source": src,
                "normalized": "",
                "tree": src,
                "reason": "already-typed",
            }
        return {
            "id": cid,
            "classification": CLASS_UNKNOWN,
            "source": src,
            "normalized": "",
            "tree": None,
            "reason": "unrecognised-tree-kind",
        }
    if not isinstance(src, str):
        return {
            "id": cid,
            "classification": CLASS_UNKNOWN,
            "source": src,
            "normalized": "",
            "tree": None,
            "reason": "non-string-stop-rule",
        }
    normalized = normalize_source(src)
    try:
        tree = parse(normalized)
    except ParseError as exc:
        return {
            "id": cid,
            "classification": CLASS_UNKNOWN,
            "source": src,
            "normalized": normalized,
            "tree": None,
            "reason": f"parse-failed:{exc}",
        }
    return {
        "id": cid,
        "classification": CLASS_EVALUABLE,
        "source": src,
        "normalized": normalized,
        "tree": tree_to_dict(tree),
        "reason": "parsed",
    }


def extract_all(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [extract_stop_rule(c) for c in candidates]


def approximate_prose_to_completeness(text: str) -> dict[str, Any]:
    """KNOWN-BROKEN control. Production extract_stop_rule must not call this.

    Maps any unmatched prose onto completeness_score >= 0.5, which is the
    silent approximation IMP-0166 forbids.
    """
    return {
        "kind": "CMP",
        "metric": "completeness_score",
        "rel": ">=",
        "value": 0.5,
        "approximated_from": text,
    }
