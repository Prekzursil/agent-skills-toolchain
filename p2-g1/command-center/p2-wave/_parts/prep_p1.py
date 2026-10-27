"""Council participant-preparation gate. IMP-0362.

Enforces the preparation/research requirement before a participant may speak.
allowed_to_speak iff: notes exist and are non-vacuous, every named source
anchor resolves, every anchor has a SUCCESSFUL fetch/read tool-call, and the
notes share a distinctive token with the fetched bytes. A bare assertion of
preparedness (asserted_prepared=True, status=asserted, or an empty tool-call
log) fires the corroboration detector and refuses the turn.

Kernel hook surface: PrepGate.require_prepared / before_turn (IMP-0264 kernel
is absent on this tree; the gate is callable, not wired).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PREP_ARTIFACT = "prep.json"
NOTES_NAME = "notes.md"

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{5,}")

FIRED_ASSERT_WITHOUT_TOOL_CALLS = "assert-prepared-without-tool-calls"
FIRED_ASSERTED_STATUS = "asserted-read-status-is-not-a-fetch"
FIRED_URL_WITHOUT_WEBFETCH = "url-without-webfetch"
FIRED_ANCHOR_WITHOUT_SUCCESS = "anchor-without-successful-fetch"
FIRED_NOTES_UNRELATED = "notes-unrelated-to-fetched-bytes"
FIRED_NOTES_VACUOUS = "notes-vacuous"


class UnpreparedError(PermissionError):
    def __init__(self, seat: str, reasons: list[str]) -> None:
        self.seat = seat
        self.reasons = list(reasons)
        super().__init__(f"seat {seat} unprepared: {','.join(self.reasons)}")


def distinctive_tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text or ""))


def resolve_anchor(anchor: str, root: Path) -> Path | None:
    """A file anchor resolves inside the seat root; URLs resolve remotely."""
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", anchor or ""):
        return None
    cand = (Path(root) / anchor).resolve()
    try:
        cand.relative_to(Path(root).resolve())
        return cand if cand.is_file() else None
    except ValueError:
        return None


def is_url(anchor: str) -> bool:
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", anchor or ""))


def load_tool_log(seat_dir: Path) -> list[dict[str, Any]]:
    log_path = Path(seat_dir) / "tool_log.json"
    if not log_path.is_file():
        return []
    try:
        doc = json.loads(log_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = doc.get("tool_calls") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]
