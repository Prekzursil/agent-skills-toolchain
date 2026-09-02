"""Named normalizers (CNF-0184 fallback when that receipt is absent)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from common import REPO, load_json

TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?")
TMP_RE = re.compile(r"/tmp/[A-Za-z0-9._-]+")
HOME_RE = re.compile(r"(/Users/[^/\s]+|/home/[^/\s]+|/root)")


def catalog() -> list[dict]:
    cnf184 = REPO / "command-center" / "receipts" / "CNF-0184.json"
    if cnf184.is_file():
        try:
            doc = load_json(cnf184)
            rows = doc.get("normalizers") or doc.get("normalizer_set") or []
            if isinstance(rows, list) and rows:
                return rows
        except (OSError, ValueError):
            pass
    return [
        {
            "id": "json-stable",
            "class": "ordering",
            "description": "Parse JSON and re-dump with sorted keys and LF newlines.",
        },
        {
            "id": "timestamp",
            "class": "timestamps",
            "description": "Replace ISO-8601 timestamps with <TIMESTAMP>.",
        },
        {
            "id": "abs-path",
            "class": "temp-paths",
            "description": "Replace home and /tmp fragments with <HOME> / <TMP>.",
        },
    ]


def apply(text: str, names: list[str]) -> str:
    out = text.replace("\r\n", "\n")
    if "timestamp" in names:
        out = TS_RE.sub("<TIMESTAMP>", out)
    if "abs-path" in names:
        out = HOME_RE.sub("<HOME>", out)
        out = TMP_RE.sub("<TMP>", out)
    if "json-stable" in names:
        try:
            obj = json.loads(out)
        except json.JSONDecodeError:
            return out
        out = json.dumps(obj, indent=1, sort_keys=True) + "\n"
    return out


def apply_file(path: Path, names: list[str]) -> str:
    return apply(path.read_text(encoding="utf-8"), names)
