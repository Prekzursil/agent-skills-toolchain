"""Inventory runtime-produced five-role first-round briefs.

Planted ADV-0092 fixtures are not a real council. Kernel stub turns of the
form 'alice:obligation:ack:N' are not participant behaviour.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator, Mapping

from common import HERE, REPO, ROLES

ROLE_ALIASES = {
    "advocate": "advocate",
    "skeptic": "skeptic",
    "domain_expert": "domain_expert",
    "domain-expert": "domain_expert",
    "domain expert": "domain_expert",
    "user_proxy": "user_proxy",
    "user-proxy": "user_proxy",
    "user proxy": "user_proxy",
    "judge": "judge",
}
SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    "scw-pull",
    "cloud-ok-2026-08-17",
    "probes",
}
SKIP_FILE_NAMES = {
    "WORK-UNIT-CATALOG.json",
    "UNIT-ARTIFACT-MANIFEST.json",
    "SUBAGENT-RETURN.json",
    "_validate_out.json",
}
BRIEF_KEYS = (
    "participant_briefs",
    "first_round_briefs",
    "produced_briefs",
)


def _norm_role(value: Any) -> str | None:
    raw = str(value or "").strip().lower().replace("-", "_")
    raw = " ".join(raw.split())
    if raw in ROLE_ALIASES:
        return ROLE_ALIASES[raw]
    spaced = raw.replace("_", " ")
    return ROLE_ALIASES.get(spaced)


def _brief_text(item: Mapping[str, Any] | Any) -> str:
    if not isinstance(item, dict):
        return ""
    for key in ("text", "body", "content", "brief", "message"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _is_stub_text(text: str) -> bool:
    t = text.strip()
    if t.count(":") >= 2 and len(t) < 80 and ":ack:" in t:
        return True
    if t.count(":") >= 2 and t.split(":")[1:2] == ["VOTE"]:
        return True
    return False


def _extract_list(obj: Any) -> list[dict[str, Any]] | None:
    if isinstance(obj, list) and obj and all(isinstance(x, dict) for x in obj):
        return obj
    if isinstance(obj, dict):
        rows = []
        for key, val in obj.items():
            if isinstance(val, dict):
                row = dict(val)
                row.setdefault("id", str(key))
                rows.append(row)
            elif isinstance(val, str) and val.strip():
                rows.append({"id": str(key), "text": val})
        return rows or None
    return None


def candidate_sets(doc: Any, rel: str) -> Iterator[dict[str, Any]]:
    def walk(node: Any, path: str) -> Iterator[dict[str, Any]]:
        if isinstance(node, dict):
            for key in BRIEF_KEYS:
                if key in node:
                    extracted = _extract_list(node[key])
                    if extracted:
                        yield {
                            "path": rel,
                            "key": key,
                            "json_path": f"{path}.{key}" if path else key,
                            "items": extracted,
                        }
            for k, v in node.items():
                nxt = f"{path}.{k}" if path else str(k)
                yield from walk(v, nxt)
        elif isinstance(node, list):
            for i, item in enumerate(node):
                yield from walk(item, f"{path}[{i}]")

    yield from walk(doc, "")


def score_set(items: list[dict[str, Any]]) -> dict[str, Any]:
    briefs = []
    roles: list[str] = []
    for i, item in enumerate(items, 1):
        text = _brief_text(item)
        role = _norm_role(item.get("role") or item.get("assigned_role") or item.get("mandate"))
        if not text or role not in ROLES:
            continue
        if _is_stub_text(text):
            continue
        bid = str(item.get("id") or item.get("participant_id") or f"p{i}")
        stance = item.get("stance") if isinstance(item.get("stance"), dict) else None
        briefs.append(
            {
                "id": bid,
                "role": role,
                "text": text,
                "stance": stance,
                "planted": False,
            }
        )
        roles.append(role)
    eligible = (
        len(briefs) == 5
        and len(set(roles)) == 5
        and set(roles) == set(ROLES)
        and all(b["text"] for b in briefs)
    )
    return {
        "n_text_and_role": len(briefs),
        "roles": roles,
        "eligible": eligible,
        "briefs": briefs if eligible else [],
        "reason": (
            "ok"
            if eligible
            else "need exactly five produced briefs with distinct roles "
            + ",".join(ROLES)
        ),
    }


def iter_json_files() -> Iterator[Path]:
    roots = [
        REPO / "command-center",
        REPO / "tools" / "council",
    ]
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.json"):
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.name in SKIP_FILE_NAMES:
                continue
            if HERE in path.parents or path.parent == HERE:
                continue
            try:
                if path.stat().st_size > 2_000_000:
                    continue
            except OSError:
                continue
            yield path


def inventory() -> dict[str, Any]:
    documents: list[str] = []
    candidates: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for path in iter_json_files():
        rel = path.relative_to(REPO).as_posix()
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        found_key = False
        for cand in candidate_sets(doc, rel):
            found_key = True
            scored = score_set(cand["items"])
            row = {
                "path": rel,
                "key": cand["key"],
                "json_path": cand["json_path"],
                "n_text_and_role": scored["n_text_and_role"],
                "roles": scored["roles"],
                "eligible": scored["eligible"],
                "reason": scored["reason"],
            }
            candidates.append(row)
            if scored["eligible"]:
                eligible.append({**row, "briefs": scored["briefs"]})
        if found_key:
            documents.append(rel)
    return {
        "inventory_rule": (
            "exactly five produced briefs with text and one distinct assigned "
            "role from advocate,skeptic,domain_expert,user_proxy,judge"
        ),
        "documents_with_participant_briefs_key": documents,
        "candidate_set_count": len(candidates),
        "eligible_real_council_count": len(eligible),
        "candidates": candidates,
        "eligible": eligible,
    }
