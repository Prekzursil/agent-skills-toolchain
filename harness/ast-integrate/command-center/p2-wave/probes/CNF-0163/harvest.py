"""Harvest file:line anchors from claims and confirmation records.

Walks structured JSON (anchor / path+line / snippet). Does not regex-scan the
catalog: prose that mentions "file:line" is use, not an evidence anchor.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from resolve import Anchor

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CORPUS_ROOTS = (
    "command-center/phase3",
    "command-center/receipts",
    "command-center/audit",
    "command-center/adversarial",
)
SKIP_NAMES = {
    "ARTIFACT-MANIFEST.json",
    "UNIT-ARTIFACT-MANIFEST.json",
    "CNF-0163.json",
}
ANCHOR_RE = re.compile(
    r"^(?P<path>[A-Za-z0-9_./-]+\.[A-Za-z0-9_-]+):(?P<line>\d+)$"
)


def parse_anchor_string(text: str) -> Optional[tuple[str, int]]:
    text = (text or "").strip().replace("\\", "/")
    m = ANCHOR_RE.match(text)
    if not m:
        return None
    path = m.group("path")
    if ".." in path.split("/"):
        return None
    return path, int(m.group("line"))


def _looks_like_path(path: str) -> bool:
    path = path.replace("\\", "/")
    if not path or path.startswith("http") or " " in path or ".." in path.split("/"):
        return False
    if "/" not in path:
        return False
    name = path.rsplit("/", 1)[-1]
    return "." in name


def _from_object(obj: dict, source: str) -> Optional[Anchor]:
    path: Optional[str] = None
    line: Optional[int] = None
    construct: Optional[str] = None
    revision: Optional[str] = None

    raw_anchor = obj.get("anchor")
    if isinstance(raw_anchor, str):
        parsed = parse_anchor_string(raw_anchor)
        if parsed:
            path, line = parsed

    p = obj.get("path")
    ln = obj.get("line")
    if isinstance(p, str) and isinstance(ln, int) and ln >= 1 and _looks_like_path(p):
        path = p.replace("\\", "/")
        line = ln

    snippet = obj.get("snippet")
    if isinstance(snippet, str) and snippet.strip():
        construct = snippet.strip()
    elif isinstance(obj.get("construct"), str) and obj["construct"].strip():
        construct = obj["construct"].strip()

    for key in ("cited_revision", "revision", "rev", "commit"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            revision = val.strip()
            break

    if not path or not line:
        return None
    if not _looks_like_path(path):
        return None
    return Anchor(
        path=path,
        line=int(line),
        construct=construct,
        revision=revision,
        cited_by=[source],
        id=f"{path}:{line}",
    )


def _walk(obj: Any, source: str, out: list[Anchor]) -> None:
    if isinstance(obj, dict):
        got = _from_object(obj, source)
        if got:
            out.append(got)
        for v in obj.values():
            _walk(v, source, out)
    elif isinstance(obj, list):
        for item in obj:
            _walk(item, source, out)


def harvest(repo: Path = REPO) -> list[Anchor]:
    found: list[Anchor] = []
    for rel in CORPUS_ROOTS:
        root = repo / rel
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.json")):
            if path.name in SKIP_NAMES:
                continue
            if any(part.startswith("_") for part in path.relative_to(repo).parts):
                continue
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            source = path.relative_to(repo).as_posix()
            _walk(doc, source, found)
    return _dedupe(found)


def _dedupe(rows: list[Anchor]) -> list[Anchor]:
    merged: dict[tuple, Anchor] = {}
    for row in rows:
        key = row.key()
        if key in merged:
            for c in row.cited_by:
                if c not in merged[key].cited_by:
                    merged[key].cited_by.append(c)
            if not merged[key].revision and row.revision:
                merged[key].revision = row.revision
        else:
            merged[key] = row
    return list(merged.values())
