"""Extract fenced shell commands from README and quick-start markdown."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

SHELL_LANGS = frozenset({"", "bash", "sh", "shell"})
FENCE_RE = re.compile(r"^```([A-Za-z0-9_-]*)[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
OPEN_FENCE_RE = re.compile(r"^```(bash|sh|shell)[ \t]*$", re.MULTILINE)
README = REPO / "README.md"
QUICKSTART = REPO / "docs" / "quickstart.md"


def _command_from_fence(body: str) -> str:
    lines: list[str] = []
    for raw in body.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def extract_file(path: Path, source_id: str) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    rows: list[dict[str, Any]] = []
    for match in FENCE_RE.finditer(text):
        lang = (match.group(1) or "").strip().lower()
        if lang not in SHELL_LANGS:
            continue
        if lang == "":
            continue
        command = _command_from_fence(match.group(2))
        if not command:
            continue
        start = text[: match.start()].count("\n") + 1
        rows.append(
            {
                "source_id": source_id,
                "path": path.relative_to(REPO).as_posix(),
                "lang": lang,
                "command": command,
                "line": start,
            }
        )
    return rows


def extract_docs() -> list[dict[str, Any]]:
    rows = extract_file(README, "README") + extract_file(QUICKSTART, "quickstart")
    for i, row in enumerate(rows, 1):
        row["id"] = f"DOC-{i:03d}"
    return rows


def independent_fence_count(path: Path) -> int:
    if not path.is_file():
        return 0
    text = path.read_text(encoding="utf-8")
    return len(OPEN_FENCE_RE.findall(text))


def audit_one_document(path: Path, source_id: str) -> dict[str, Any]:
    extracted = extract_file(path, source_id)
    independent = independent_fence_count(path)
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    missing = [row["command"] for row in extracted if row["command"] not in text]
    return {
        "path": path.relative_to(REPO).as_posix() if path.is_file() else str(path),
        "source_id": source_id,
        "extracted_count": len(extracted),
        "independent_fence_count": independent,
        "counts_match": len(extracted) == independent,
        "bodies_present_in_source": not missing,
        "missing_bodies": missing,
        "commands": [row["command"] for row in extracted],
    }
