"""Independent substance-collapse reviewer for ADV-0135.

Uses tools.council.quota.unique_ideas (RES-0084 / TST-0265 counter):
union-find on the author path, connected-components on the reviewer path.
A council is COLLAPSED when every seat's substance_claim merges to one
cluster. Vote labels, declared roles, generation_ids, and dissent sidecars
are ignored — those are the surfaces the shipped controls measure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.council.quota.unique_ideas import (  # noqa: E402
    unique_count_connected_components,
    unique_count_union_find,
)


def claims_of(council: dict[str, Any]) -> list[str]:
    seats = council.get("participants") or []
    out: list[str] = []
    for seat in seats:
        if not isinstance(seat, dict):
            continue
        claim = str(seat.get("substance_claim") or "").strip()
        if claim:
            out.append(claim)
    return out


def _cluster_n(value: Any) -> int:
    """Live unique_ideas counters return int or {unique_count, components, n}."""
    if value is None:
        return 0
    if isinstance(value, dict):
        if "unique_count" in value:
            return int(value["unique_count"])
        if "n" in value:
            return int(value["n"])
        return 0
    return int(value)


def cluster_counts(council: dict[str, Any]) -> dict[str, int]:
    claims = claims_of(council)
    return {
        "n_claims": len(claims),
        "union_find": _cluster_n(
            unique_count_union_find(claims) if claims else 0
        ),
        "connected_components": _cluster_n(
            unique_count_connected_components(claims) if claims else 0
        ),
    }


def classify(council: dict[str, Any]) -> dict[str, Any]:
    """Label-blind: does not read attack_id, name, or defeated_control."""
    blind = json.loads(json.dumps(council))
    for key in ("attack_id", "name", "defeated_control", "slipped_assertion", "kind"):
        blind.pop(key, None)
    counts = cluster_counts(blind)
    n = counts["connected_components"]
    collapsed = n == 1 and counts["n_claims"] >= 2
    return {
        "class": "collapsed" if collapsed else "healthy",
        "collapsed": collapsed,
        "substance_clusters": n,
        "author_clusters": counts["union_find"],
        "n_claims": counts["n_claims"],
        "algorithm": "connected-components-vs-union-find",
        "labels_hidden": True,
    }
