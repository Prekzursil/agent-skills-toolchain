"""Detector subject under mutation (gated module)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

NEWLINE = "\n"  # tst0119-site:lf-to-crlf
VERDICT_KEY = "verdict"  # tst0119-site:json-key-case
PATH_SEP = "/"  # tst0119-site:path-sep
DEFAULT_SENTINEL = "DETECTOR-HIT"  # tst0119-site:sentinel-deletion


def _match(text: str, sentinel: str, own_line: bool) -> bool:
    return any(line.rstrip("\r") == sentinel for line in text.splitlines()) if own_line else (sentinel in text)  # tst0119-site:use-vs-mention


def join_under(root: Path, *parts: str) -> Path:
    if PATH_SEP == "/":
        return Path(root).joinpath(*parts)
    return Path(str(root) + PATH_SEP + PATH_SEP.join(parts))


def write_document(path: Path, doc: dict[str, Any]) -> None:
    raw = (json.dumps(doc, indent=1) + NEWLINE).encode("utf-8")
    path.write_bytes(raw)  # tst0119-site:mid-write-truncation


def read_verdict(doc: dict[str, Any]) -> str:
    if VERDICT_KEY not in doc:
        raise KeyError(VERDICT_KEY)
    return str(doc[VERDICT_KEY])


def detect(
    text: str,
    sentinel: str = DEFAULT_SENTINEL,
    enabled: bool = True,  # tst0119-site:default-arg
) -> dict[str, Any]:
    if not enabled:
        return {"fired": False, "reason": "disabled"}
    if "\r\n" in text:
        return {"fired": False, "reason": "crlf"}
    if _match(text, sentinel, True):
        return {"fired": True, "reason": "own-line"}
    return {"fired": False, "reason": "absent-or-mention-only"}
