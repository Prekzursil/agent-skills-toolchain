"""Owner/project ban/pin beat router.score (IMP-0394)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PRECEDENCE_TABLE = [
    {"layer": "owner.ban", "rank": 1},
    {"layer": "project.ban", "rank": 2},
    {"layer": "owner.pin", "rank": 3},
    {"layer": "project.pin", "rank": 4},
    {"layer": "router.score", "rank": 5},
]


@dataclass
class Overlay:
    owner_ban: set[str] = field(default_factory=set)
    project_ban: set[str] = field(default_factory=set)
    owner_pin: set[str] = field(default_factory=set)
    project_pin: set[str] = field(default_factory=set)
    project_key: str | None = None


def printed_precedence() -> str:
    lines = [f"{i}. {row['layer']}" for i, row in enumerate(PRECEDENCE_TABLE, 1)]
    return "\n".join(lines)


def _collect(block: dict[str, Any]) -> tuple[set[str], set[str]]:
    ov = block.get("capabilityOverrides") or block.get("overrides") or block
    bans: set[str] = set()
    pins: set[str] = set()
    if not isinstance(ov, dict):
        return bans, pins
    raw_ban = ov.get("ban") or ov.get("bans") or []
    raw_pin = ov.get("pin") or ov.get("pins") or []
    if isinstance(raw_ban, str):
        raw_ban = [raw_ban]
    if isinstance(raw_pin, str):
        raw_pin = [raw_pin]
    for row in raw_ban:
        cid = row if isinstance(row, str) else str((row or {}).get("capability_id") or (row or {}).get("id") or "")
        if cid:
            bans.add(cid)
    for row in raw_pin:
        cid = row if isinstance(row, str) else str((row or {}).get("capability_id") or (row or {}).get("id") or "")
        if cid:
            pins.add(cid)
    return bans, pins


def load_overlay(user: Path, project: Path, project_key: str | None = None) -> Overlay:
    ov = Overlay()
    u = json.loads(Path(user).read_text(encoding="utf-8")) if Path(user).is_file() else {}
    p = json.loads(Path(project).read_text(encoding="utf-8")) if Path(project).is_file() else {}
    ub, up = _collect(u)
    pb, pp = _collect(p)
    ov.owner_ban |= ub
    ov.owner_pin |= up
    ov.project_ban |= pb
    ov.project_pin |= pp
    ov.project_key = project_key  # type: ignore[attr-defined]
    return ov


def classify(capability_id: str, overlay: Overlay) -> str:
    if capability_id in overlay.owner_ban:
        return "owner.ban"
    if capability_id in overlay.project_ban:
        return "project.ban"
    if capability_id in overlay.owner_pin:
        return "owner.pin"
    if capability_id in overlay.project_pin:
        return "project.pin"
    return "router.score"


def apply_overrides(
    named: list[dict[str, Any]], overlay: Overlay, ceiling: int | float
) -> dict[str, Any]:
    admitted: list[str] = []
    excluded: list[dict[str, Any]] = []
    pinned: list[str] = []
    scored: list[dict[str, Any]] = []
    layers: dict[str, str] = {}
    for cap in named:
        cid = str(cap.get("capability_id") or cap.get("id") or "")
        layer = classify(cid, overlay)
        layers[cid] = layer
        if layer in {"owner.ban", "project.ban"}:
            excluded.append({"capability_id": cid, "layer": layer, "reason": layer})
            continue
        if layer in {"owner.pin", "project.pin"}:
            pinned.append(cid)
            admitted.append(cid)
            continue
        scored.append(cap)
    # score remainder under ceiling
    scored.sort(key=lambda c: float(c.get("score") or 0.0), reverse=True)
    budget = float(ceiling)
    used = 0.0
    for cap in scored:
        cid = str(cap.get("capability_id") or cap.get("id") or "")
        score = float(cap.get("score") or 0.0)
        if score <= 0.0:
            # router.score admits only positive evidence; a zero score is the
            # sibling-project view of another project's pin and must not leak.
            excluded.append({"capability_id": cid, "layer": "router.score", "reason": "no-score"})
            continue
        cost = float(cap.get("token_cost") or cap.get("cost") or 0.0)
        if used + cost <= budget or budget >= 10000:
            admitted.append(cid)
            used += cost
        else:
            excluded.append({"capability_id": cid, "layer": "router.score", "reason": "budget"})
    return {
        "admitted_ids": admitted,
        "excluded": excluded,
        "pinned_ids": pinned,
        "printed_precedence": printed_precedence(),
        "project_id": overlay.project_key,
        "project_key": overlay.project_key,
        "session_key": ["project", overlay.project_key],
        "layers": layers,
        "precedence_layers": [row["layer"] for row in PRECEDENCE_TABLE],
    }
