"""Fixture workflows, conflict edges, and optional live-dep loaders for WFA-0102.

Live WFA-0062 / WFA-0081 artifacts are consumed when present. When absent the
operator still runs against the catalog-named HARD pairs (independent first
pass vs shared-context deliberation, deterministic replay vs non-deterministic
sampling, fire-and-forget vs blocking fan-in). That stand-in is labelled
fixture, not a claim that those units delivered.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fusion_union import DEFAULT_CONFLICT_EDGES, HARD, SOFT

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

LIVE_CONFLICTS = REPO / "command-center/wfa/WFA-0062-mechanism-conflicts.json"
LIVE_MERGE_MAP = REPO / "command-center/wfa/WFA-0081-merge-compatibility-map-v2.json"
LIVE_DIFF = REPO / "command-center/wfa/WFA-0094-semantic-diff-engine.json"


def workflow_alpha() -> dict[str, Any]:
    """Deterministic review pipeline. Collides with beta on ingest/emit/researcher."""
    return {
        "id": "wf-alpha",
        "stages": [
            {
                "id": "ingest",
                "role_id": "researcher",
                "gate_ids": [],
                "depends_on": [],
                "mechanisms": ["extract-text", "independent-first-pass"],
            },
            {
                "id": "review",
                "role_id": "reviewer",
                "gate_ids": ["confidence-floor"],
                "depends_on": ["ingest"],
                "mechanisms": ["deterministic-replay", "blocking-fan-in"],
            },
            {
                "id": "emit",
                "role_id": "reviewer",
                "gate_ids": ["confidence-floor"],
                "depends_on": ["review"],
                "mechanisms": ["publish-record"],
            },
        ],
        "roles": [
            {
                "id": "researcher",
                "permissions": ["read-corpus"],
                "mechanisms": ["sequential-schedule"],
            },
            {
                "id": "reviewer",
                "permissions": ["approve-or-reject"],
                "mechanisms": [],
            },
        ],
        "gates": [
            {
                "id": "confidence-floor",
                "rule": "score >= 0.8",
                "mechanisms": ["confidence-threshold"],
            }
        ],
    }


def workflow_beta() -> dict[str, Any]:
    """Compatible compose pipeline. Unique mechs live on colliding names.

    ingest carries fetch-url (alpha's ingest carries extract-text). An overwrite
    of ingest silently drops extract-text — the named capability-loss.
    """
    return {
        "id": "wf-beta",
        "stages": [
            {
                "id": "ingest",
                "role_id": "researcher",
                "gate_ids": ["budget-cap"],
                "depends_on": [],
                "mechanisms": ["fetch-url", "independent-first-pass"],
            },
            {
                "id": "compose",
                "role_id": "composer",
                "gate_ids": ["budget-cap"],
                "depends_on": ["ingest"],
                "mechanisms": ["synthesise-draft"],
            },
            {
                "id": "emit",
                "role_id": "composer",
                "gate_ids": ["budget-cap"],
                "depends_on": ["compose"],
                "mechanisms": ["publish-record", "schema-validate"],
            },
        ],
        "roles": [
            {
                "id": "researcher",
                "permissions": ["read-web"],
                "mechanisms": [],
            },
            {
                "id": "composer",
                "permissions": ["write-draft"],
                "mechanisms": [],
            },
        ],
        "gates": [
            {
                "id": "budget-cap",
                "rule": "tokens <= 8000",
                "mechanisms": ["token-budget"],
            }
        ],
    }


def workflow_gamma() -> dict[str, Any]:
    """Conflicts with alpha: shared-context deliberation + non-deterministic sampling."""
    return {
        "id": "wf-gamma",
        "stages": [
            {
                "id": "ingest",
                "role_id": "facilitator",
                "gate_ids": [],
                "depends_on": [],
                "mechanisms": ["harvest-notes"],
            },
            {
                "id": "debate",
                "role_id": "facilitator",
                "gate_ids": ["open-floor"],
                "depends_on": ["ingest"],
                "mechanisms": [
                    "shared-context-deliberation",
                    "non-deterministic-sampling",
                ],
            },
            {
                "id": "emit",
                "role_id": "facilitator",
                "gate_ids": [],
                "depends_on": ["debate"],
                "mechanisms": ["publish-record"],
            },
        ],
        "roles": [
            {
                "id": "facilitator",
                "permissions": ["moderate"],
                "mechanisms": [],
            }
        ],
        "gates": [
            {
                "id": "open-floor",
                "rule": "no-unilateral-close",
                "mechanisms": [],
            }
        ],
    }


def workflow_delta() -> dict[str, Any]:
    """SOFT-awkward with alpha (parallel vs sequential schedule). Must still union."""
    return {
        "id": "wf-delta",
        "stages": [
            {
                "id": "ingest",
                "role_id": "scout",
                "gate_ids": [],
                "depends_on": [],
                "mechanisms": ["extract-text"],
            },
            {
                "id": "fanout",
                "role_id": "scout",
                "gate_ids": [],
                "depends_on": ["ingest"],
                "mechanisms": ["parallel-schedule"],
            },
            {
                "id": "emit",
                "role_id": "scout",
                "gate_ids": [],
                "depends_on": ["fanout"],
                "mechanisms": ["publish-record"],
            },
        ],
        "roles": [{"id": "scout", "permissions": ["read-corpus"], "mechanisms": []}],
        "gates": [],
    }


def task_mechanisms() -> list[str]:
    """Matched-pair task: unique mechs from alpha and beta. Stage count is irrelevant."""
    return ["extract-text", "fetch-url", "synthesise-draft"]


def _edges_from_live(doc: dict[str, Any]) -> list[tuple[str, str, str]] | None:
    raw = (
        doc.get("conflict_edges")
        or doc.get("conflicts")
        or doc.get("edges")
        or doc.get("pairs")
    )
    if not isinstance(raw, list) or not raw:
        return None
    out: list[tuple[str, str, str]] = []
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            a, b = str(item[0]), str(item[1])
            grade = str(item[2]).upper() if len(item) > 2 else HARD
            if a and b:
                out.append((a, b, HARD if grade == HARD else SOFT))
            continue
        if isinstance(item, dict):
            a = str(item.get("a") or item.get("left") or item.get("from") or "")
            b = str(item.get("b") or item.get("right") or item.get("to") or "")
            grade = str(item.get("grade") or item.get("kind") or HARD).upper()
            if a and b:
                out.append((a, b, HARD if grade == HARD else SOFT))
    return out or None


def load_conflict_edges() -> tuple[list[tuple[str, str, str]], str]:
    if LIVE_CONFLICTS.is_file() and LIVE_CONFLICTS.stat().st_size > 0:
        try:
            doc = json.loads(LIVE_CONFLICTS.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            doc = None
        if isinstance(doc, dict):
            parsed = _edges_from_live(doc)
            if parsed:
                return parsed, f"live:{LIVE_CONFLICTS.relative_to(REPO).as_posix()}"
    return list(DEFAULT_CONFLICT_EDGES), "fixture-stand-in:WFA-0062-absent"


def load_merge_map_note() -> dict[str, Any]:
    if LIVE_MERGE_MAP.is_file() and LIVE_MERGE_MAP.stat().st_size > 0:
        return {
            "origin": f"live:{LIVE_MERGE_MAP.relative_to(REPO).as_posix()}",
            "present": True,
        }
    return {
        "origin": "fixture-stand-in:WFA-0081-absent",
        "present": False,
        "fusible_pairs": [["wf-alpha", "wf-beta"], ["wf-alpha", "wf-delta"]],
        "refused_pairs": [["wf-alpha", "wf-gamma"]],
        "note": (
            "v2 merge map is not on this tree. Pair legality for this unit is "
            "the mechanism-conflict check itself (HARD edges refuse)."
        ),
    }


def load_diff_note() -> dict[str, Any]:
    if LIVE_DIFF.is_file() and LIVE_DIFF.stat().st_size > 0:
        return {
            "origin": f"live:{LIVE_DIFF.relative_to(REPO).as_posix()}",
            "present": True,
        }
    return {
        "origin": "fixture-stand-in:WFA-0094-absent",
        "present": False,
        "collision_predicate": "structural-id-equality",
        "note": (
            "Semantic differ is not on this tree. Name collisions are detected "
            "by IR id equality (stage/role/gate), which is the overwrite failure "
            "mode the unit names. Semantic-but-distinct names are not collapsed."
        ),
    }


workflow_alpha = workflow_alpha
workflow_beta = workflow_beta
workflow_gamma = workflow_gamma
workflow_delta = workflow_delta
load_conflict_edges = load_conflict_edges
task_mechanisms = task_mechanisms
