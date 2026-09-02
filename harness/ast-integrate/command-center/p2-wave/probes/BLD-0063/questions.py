"""Canonical eleven Phase 13 questions for BLD-0063.

The spec cites _USER-PROMPTS.md:11069-11080. That file is not on this
worktree. The eleven labels are the distinct catalog tags on BLD-0001
through BLD-0062, excluding the meta disposition tag at :11082.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

TAG_RE = re.compile(
    r"\[Phase 13 question answered:\s*(.+?)\]\s*$",
    re.DOTALL,
)

ELEVEN: tuple[tuple[str, str], ...] = (
    ("Q01", "what files were never read"),
    ("Q02", "what clients were never tested"),
    ("Q03", "what platforms were never tested"),
    ("Q04", "what owner requirements disappeared"),
    ("Q05", "what option IDs were silently dropped"),
    ("Q06", "what failures were normalized away"),
    ("Q07", "what unknowns remain"),
    ("Q08", "what existing work was ignored"),
    ("Q09", "what test could falsely pass"),
    ("Q10", "what threat actor was not modeled"),
    ("Q11", "what would break at 10x scale"),
)

QUESTION_BY_ID = {qid: label for qid, label in ELEVEN}
ID_BY_QUESTION = {label: qid for qid, label in ELEVEN}
ELEVEN_LABELS = frozenset(QUESTION_BY_ID.values())

META_PREFIX = "meta: completeness of the blind-spot review itself"

SELF_ID = "BLD-0063"
INPUT_IDS = tuple(f"BLD-{i:04d}" for i in range(1, 63))


def parse_tag(question_or_target: str) -> str | None:
    if not isinstance(question_or_target, str):
        return None
    m = TAG_RE.search(question_or_target.strip())
    if not m:
        return None
    return m.group(1).strip()


def is_meta(tag: str | None) -> bool:
    return bool(tag) and tag.startswith("meta:")


def load_catalog_units(catalog_path: Path) -> dict[str, dict]:
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for unit in data.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        uid = unit.get("id")
        if isinstance(uid, str) and uid.startswith("BLD-"):
            out[uid] = unit
    return out


def planned_by_question(catalog_units: dict[str, dict]) -> dict[str, list[str]]:
    planned = {label: [] for label in ELEVEN_LABELS}
    for uid in INPUT_IDS:
        unit = catalog_units.get(uid) or {}
        tag = parse_tag(str(unit.get("question_or_target") or ""))
        if tag in planned:
            planned[tag].append(uid)
    return planned


def first_unit_for_each_question(catalog_units: dict[str, dict]) -> dict[str, str]:
    first: dict[str, str] = {}
    for uid in INPUT_IDS:
        unit = catalog_units.get(uid) or {}
        tag = parse_tag(str(unit.get("question_or_target") or ""))
        if tag in ELEVEN_LABELS and tag not in first:
            first[tag] = uid
    return first
