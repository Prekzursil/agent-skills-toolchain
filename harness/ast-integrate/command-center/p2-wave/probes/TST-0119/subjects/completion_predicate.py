"""Completion-predicate subject under mutation (gated module)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

NEWLINE = "\n"  # tst0119-site:lf-to-crlf
STATE_KEY = "state"  # tst0119-site:json-key-case
PATH_SEP = "/"  # tst0119-site:path-sep
DEFAULT_SENTINEL = "SUCCESS:MODULE"  # tst0119-site:sentinel-deletion


def _match(text: str, sentinel: str, own_line: bool) -> bool:
    return any(line.rstrip("\r") == sentinel for line in text.splitlines()) if own_line else (sentinel in text)  # tst0119-site:use-vs-mention


def join_under(root: Path, *parts: str) -> Path:
    if PATH_SEP == "/":
        return Path(root).joinpath(*parts)
    return Path(str(root) + PATH_SEP + PATH_SEP.join(parts))


def write_document(path: Path, doc: dict[str, Any]) -> None:
    raw = (json.dumps(doc, indent=1) + NEWLINE).encode("utf-8")
    path.write_bytes(raw)  # tst0119-site:mid-write-truncation


def read_state(doc: dict[str, Any]) -> str:
    if STATE_KEY not in doc:
        raise KeyError(STATE_KEY)
    return str(doc[STATE_KEY])


def check_artifact(
    text: str,
    sentinel: str = DEFAULT_SENTINEL,
    require_own_line: bool = True,  # tst0119-site:default-arg
) -> dict[str, Any]:
    if "\r\n" in text:
        return {"ok": False, "reason": "crlf"}
    try:
        doc, _end = json.JSONDecoder().raw_decode(text.lstrip())
    except json.JSONDecodeError as exc:
        return {"ok": False, "reason": f"unparseable:{exc}"}
    if not isinstance(doc, dict):
        return {"ok": False, "reason": "not-object"}
    try:
        state = read_state(doc)
    except KeyError:
        return {"ok": False, "reason": "missing-state-key"}
    if not _match(text, sentinel, require_own_line):
        return {"ok": False, "reason": "sentinel-missing-or-mention-only", "state": state}
    return {"ok": True, "reason": "pass", "state": state}
