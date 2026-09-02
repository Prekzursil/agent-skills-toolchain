"""Reverse-trace a claim record to its cited source span."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from contract import REPO


def _open_path(rel_or_abs: str) -> Path:
    p = Path(rel_or_abs)
    if p.is_absolute():
        return p
    return REPO / rel_or_abs


def reverse_trace(record: dict[str, Any], *, snippet_override: str | None = None) -> dict[str, Any]:
    lineage = record.get("source_lineage") or []
    if not lineage or not isinstance(lineage[0], dict):
        return {"ok": False, "reason": "lineage-missing"}
    loc = lineage[0]
    path = _open_path(str(loc.get("path") or ""))
    line_no = int(loc.get("line") or 0)
    snippet = snippet_override if snippet_override is not None else str(loc.get("snippet") or "")
    out = {
        "ok": False,
        "path": str(loc.get("path") or ""),
        "line": line_no,
        "file_exists": path.is_file(),
        "snippet": snippet,
        "line_content": None,
        "reason": "unchecked",
        "claim_id": record.get("claim_id"),
    }
    if not path.is_file():
        out["reason"] = "file-missing"
        return out
    if line_no < 1:
        out["reason"] = "line-unparsed"
        return out
    lines = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").split(
        "\n"
    )
    if line_no > len(lines):
        out["reason"] = "line-oob"
        return out
    content = lines[line_no - 1]
    out["line_content"] = content
    if not snippet:
        out["reason"] = "snippet-empty"
        return out
    if snippet not in content:
        out["reason"] = "snippet-not-in-line"
        return out
    mech = str(record.get("canonical_mechanism") or "")
    token = snippet if len(snippet) <= 24 else snippet[:24]
    says_source = bool(mech) and (token in mech or snippet in mech)
    out["ok"] = bool(says_source)
    out["reason"] = "matched" if out["ok"] else "mechanism-ungrounded"
    return out
