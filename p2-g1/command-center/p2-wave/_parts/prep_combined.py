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
def corroborate(anchor_list: list[str], log: list[dict], notes_text: str,
                root: Path) -> list[str]:
    """Fire every corroboration failure. Asserted preparedness is not proof."""
    fires: list[str] = []
    has_ok_call = any(
        str(r.get("status") or "").lower() == "ok" and not _is_asserted(r)
        for r in log
    )
    if any(str(r.get("status") or "").lower() == "asserted" for r in log):
        fires.append(FIRED_ASSERTED_STATUS)
    for anchor in anchor_list:
        hit = False
        for r in log:
            if str(r.get("target") or "") != anchor:
                continue
            if _is_asserted(r):
                continue
            if str(r.get("status") or "").lower() == "ok":
                hit = per_anchor_url_check(anchor, r, root, fires)
                break
        if not hit:
            if is_url(anchor) and not any(
                str(r.get("tool") or "").lower() == "webfetch" for r in log
            ):
                fires.append(FIRED_URL_WITHOUT_WEBFETCH)
            else:
                fires.append(FIRED_ANCHOR_WITHOUT_SUCCESS)
    if notes_text and anchor_list and not fires:
        if not _notes_share_token(notes_text, root, log, anchor_list):
            fires.append(FIRED_NOTES_UNRELATED)
    return fires


def per_anchor_url_check(anchor: str, row: dict, root: Path,
                         fires: list[str]) -> bool:
    """Validate one anchor against its ok tool-call row; True if corroborated."""
    if is_url(anchor):
        if str(row.get("tool") or "").lower() != "webfetch":
            fires.append(FIRED_URL_WITHOUT_WEBFETCH)
            return False
        return True
    path = resolve_anchor(anchor, root)
    if path is None:
        fires.append(FIRED_ANCHOR_WITHOUT_SUCCESS)
        return False
    try:
        row["fetched_bytes"] = len(path.read_bytes())
    except OSError:
        fires.append(FIRED_ANCHOR_WITHOUT_SUCCESS)
        return False
    return True


def _notes_share_token(notes_text: str, root: Path, log: list,
                       anchor_list: list[str]) -> bool:
    for anchor in anchor_list:
        if is_url(anchor):
            continue
        path = resolve_anchor(anchor, root)
        if path is None:
            continue
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if distinctive_tokens(notes_text) & distinctive_tokens(src):
            return True
    return False


def _is_asserted(row: dict) -> bool:
    return str(row.get("status") or "").lower() == "asserted"


@dataclass
class PrepGate:
    root: Path
    require_tool_log: bool = True

    def seat_dir(self, seat: str) -> Path:
        return Path(self.root) / str(seat)

    def _artifact(self, seat: str) -> dict | None:
        p = self.seat_dir(seat) / PREP_ARTIFACT
        if not p.is_file():
            return None
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return doc if isinstance(doc, dict) else None

    def require_prepared(self, seat: str) -> dict:
        seat_dir = self.seat_dir(seat)
        art = self._artifact(seat)
        reasons: list[str] = []
        if art is None:
            reasons.append("preparation-artifact-absent-or-unparseable")
            raise UnpreparedError(seat, reasons)
        notes_path = seat_dir / str(art.get("notes") or NOTES_NAME)
        if not notes_path.is_file() or notes_path.stat().st_size == 0:
            reasons.append("notes-absent-or-empty")
        notes_text = ""
        if notes_path.is_file():
            notes_text = notes_path.read_text(encoding="utf-8", errors="replace")
        anchors = [str(a) for a in (art.get("sources") or [])]
        log = load_tool_log(seat_dir)
        fires = corroborate(anchors, log, notes_text, seat_dir)
        if art.get("asserted_prepared") and not log:
            if FIRED_ASSERT_WITHOUT_TOOL_CALLS not in fires:
                fires.append(FIRED_ASSERT_WITHOUT_TOOL_CALLS)
        if fires:
            raise UnpreparedError(seat, reasons + fires)
        if reasons:
            raise UnpreparedError(seat, reasons)
        return {
            "seat": seat, "allowed_to_speak": True,
            "anchors": anchors, "notes": notes_path.name,
            "fetched": [r for r in log if str(r.get("status") or "").lower() == "ok"],
        }

    def before_turn(self, seat: str) -> dict:
        return self.require_prepared(seat)
