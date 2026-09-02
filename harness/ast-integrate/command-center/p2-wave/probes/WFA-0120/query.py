#!/usr/bin/env python3
"""Local typed query over the WFA-0120 control corpus.

WFA-0084 (registry query interface) is not delivered on this worktree.
This module is the gate's consumption contract: callers query by route,
state, mechanism and kind. A miss returns an empty list, never an error
that a caller could read as zero-by-crash. Versioned: bump INTERFACE_VERSION
when the result shape changes.
"""
from __future__ import annotations

from typing import Any, Mapping

from gate import mechanisms_of

INTERFACE_VERSION = "wfa-0120-local-query-v1"
ARTIFACT_VERSION = "control-corpus-v1"


def _blueprints(corpus: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = corpus.get("blueprints") or []
    return [r for r in rows if isinstance(r, dict)]


def _registry(corpus: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = corpus.get("registry") or []
    return [r for r in rows if isinstance(r, dict)]


def registry_candidates(corpus: Mapping[str, Any]) -> list[dict[str, Any]]:
    return _registry(corpus)


def by_route(corpus: Mapping[str, Any], route: str) -> list[dict[str, Any]]:
    return [r for r in _blueprints(corpus) if str(r.get("route") or "") == route]


def by_state(corpus: Mapping[str, Any], state: str) -> list[dict[str, Any]]:
    return [r for r in _blueprints(corpus) if str(r.get("state") or "") == state]


def by_mechanism(corpus: Mapping[str, Any], mech_id: str) -> list[dict[str, Any]]:
    hits = []
    for r in _registry(corpus):
        if mech_id in mechanisms_of(r):
            hits.append(r)
    return hits


def empty_result() -> dict[str, Any]:
    return {
        "interface_version": INTERFACE_VERSION,
        "artifact_version": ARTIFACT_VERSION,
        "matches": [],
        "empty": True,
    }


def wrap(matches: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "interface_version": INTERFACE_VERSION,
        "artifact_version": ARTIFACT_VERSION,
        "matches": matches,
        "empty": len(matches) == 0,
        "count": len(matches),
    }
