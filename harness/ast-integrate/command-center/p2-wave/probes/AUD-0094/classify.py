"""Use-versus-mention classification for deleted-path hits."""
from __future__ import annotations

import re
from pathlib import Path

MENTION_NAME = re.compile(
    r"(changelog|history|news|retirement-lane|decision-log)",
    re.IGNORECASE,
)
MENTION_LINE = re.compile(
    r"(?i)\b(deleted|removed|retired|delete-all|retirement|do not restore)\b"
)
USE_LINE = re.compile(
    r"(?i)(\bimport\b|\bfrom\b|\brequire\s*\(|\binclude\s+|open\s*\(|"
    r"Path\s*\(|pathlib|importlib|pytest |python3?\s|run:\s|entry[\"']?\s*:)"
)
CATALOG_MENTION_HINT = re.compile(
    r"(?i)(question_or_target|DELETE-ALL|77 files|dangling|retirement blast)"
)


def _is_catalog(rel: str) -> bool:
    name = Path(rel).name
    return name == "WORK-UNIT-CATALOG.json" or "WORK-UNIT-CATALOG" in rel


def _is_changelog(rel: str) -> bool:
    name = Path(rel).name
    if MENTION_NAME.search(name):
        return True
    return "CHANGELOG" in rel.replace("\\", "/")


def classify_hit(rel: str, line: str, deleted_path: str) -> str:
    """Return USE or MENTION for one (file, line, deleted_path) hit."""
    rel_n = rel.replace("\\", "/")
    stripped = line.strip()
    if _is_changelog(rel_n):
        return "MENTION"
    if _is_catalog(rel_n):
        return "MENTION"
    if stripped.startswith("#") or stripped.startswith("//"):
        if MENTION_LINE.search(line) or not USE_LINE.search(line):
            return "MENTION"
    if MENTION_LINE.search(line) and not USE_LINE.search(line):
        return "MENTION"
    if CATALOG_MENTION_HINT.search(line) and not USE_LINE.search(line):
        return "MENTION"
    ext = Path(rel_n).suffix.lower()
    if ext in {".md", ".rst", ".txt"} and not USE_LINE.search(line):
        return "MENTION"
    return "USE"


def is_mention_only(hits: list[dict], deleted_path: str) -> bool:
    kinds = [h["kind"] for h in hits if h["deleted_path"] == deleted_path]
    return bool(kinds) and all(k == "MENTION" for k in kinds)
