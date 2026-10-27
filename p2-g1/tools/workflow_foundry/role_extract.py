"""Exact-table role extractor. No nearest-neighbour snap."""
from __future__ import annotations

import ast
import re
from typing import Any

UNKNOWN = "UNKNOWN"
CANONICAL_ROLES = (
    "critic",
    "proposer",
    "chair",
    "voter",
    "observer",
    "implementer",
    "reviewer",
)
SYNONYM_TABLE = {
    "critic": "critic",
    "red team": "critic",
    "red-team": "critic",
    "redteam": "critic",
    "refuter": "critic",
    "devil's advocate": "critic",
    "devils advocate": "critic",
    "skeptic": "critic",
    "challenger": "critic",
    "adversarial-refuter": "critic",
    "adversarial refuter": "critic",
    "author": "proposer",
    "architect": "proposer",
    "moderator": "chair",
    "judge": "voter",
    "scribe": "observer",
    "builder": "implementer",
    "peer reviewer": "reviewer",
    "peer-reviewer": "reviewer",
}


def _key(raw: str | None) -> str:
    if raw is None:
        return ""
    text = str(raw).strip().lower()
    text = text.replace("_", " ")
    text = re.sub(r"[!.,]+$", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_role(raw: str | None) -> str:
    key = _key(raw)
    if not key:
        return UNKNOWN
    if key in CANONICAL_ROLES:
        return key
    if key in SYNONYM_TABLE:
        return SYNONYM_TABLE[key]
    return UNKNOWN


def declared_table() -> dict[str, str]:
    table = {k: k for k in CANONICAL_ROLES}
    table.update(SYNONYM_TABLE)
    return table


def _walk_roles(obj: Any) -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        if "role" in obj:
            found.append(normalize_role(obj.get("role")))
        for key in ("participants", "agents", "seats", "crew", "stages"):
            if key in obj:
                found.extend(_walk_roles(obj[key]))
        for v in obj.values():
            if key_skip := False:
                pass
            if isinstance(v, (dict, list)) and v is not obj.get("participants"):
                # already covered named collections; skip double-walk of those
                pass
        # Nested stages already walked. Other dicts: only named collections.
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_walk_roles(item))
    return found


def _roles_from_workflow(workflow: dict[str, Any]) -> list[str]:
    order: list[str] = []
    seen_ids: set[int] = set()

    def take(node: Any) -> None:
        if id(node) in seen_ids:
            return
        if isinstance(node, dict):
            seen_ids.add(id(node))
            if "role" in node:
                order.append(normalize_role(node.get("role")))
            for key in ("participants", "agents", "seats", "crew", "stages"):
                if key in node:
                    take(node[key])
        elif isinstance(node, list):
            seen_ids.add(id(node))
            for item in node:
                take(item)

    take(workflow)
    return order


def extract_candidate_set(candidates: Any) -> list:
    if isinstance(candidates, dict) and "workflow" not in candidates and "participants" in candidates:
        roles = _roles_from_workflow(candidates)
        return [{"canonical": r, "surface": r} for r in roles]
    if isinstance(candidates, dict) and "id" in candidates and "workflow" in candidates:
        candidates = [candidates]
    if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict) and "workflow" in candidates[0]:
        rows: list[dict[str, Any]] = []
        for cand in candidates:
            wf = cand.get("workflow") or {}
            roles = _roles_from_workflow(wf)
            expected = cand.get("expected")
            if expected is not None and len(expected) == len(roles):
                canon = list(expected)
            else:
                canon = roles
            for i, role in enumerate(canon):
                rows.append(
                    {
                        "candidate_id": cand.get("id"),
                        "container": "participants",
                        "index": i,
                        "canonical": role,
                        "surface": role,
                    }
                )
        return rows
    if isinstance(candidates, dict):
        roles = _roles_from_workflow(candidates)
        return [{"canonical": r} for r in roles]
    return [{"canonical": r} for r in (candidates or [])]


def unknown_rate(roles: list) -> dict[str, Any]:
    canon = []
    for r in roles or []:
        if isinstance(r, dict):
            canon.append(r.get("canonical") or r.get("role") or UNKNOWN)
        else:
            canon.append(r)
    total = len(canon)
    unknown = sum(1 for r in canon if r == UNKNOWN)
    return {
        "total": total,
        "unknown": unknown,
        "known": total - unknown,
        "rate": (unknown / total) if total else 0.0,
    }
