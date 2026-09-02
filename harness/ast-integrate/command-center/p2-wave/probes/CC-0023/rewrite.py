"""Detect unattributed M-NN rewrites. An attributed owner rewrite must cite CC-0023."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])M-(\d{1,2})(?!\d)")
ATTR_RE = re.compile(r"CC-0023|owner.?answer|OWNER-DECISIONS", re.I)


def digest_text(text: str) -> str:
    raw = text.replace("\r\n", "\n").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def tokens(text: str) -> list[str]:
    return [f"M-{int(m.group(1))}" for m in TOKEN_RE.finditer(text)]


def silent_rewrites(before: str, after: str) -> list[dict[str, str]]:
    """Return tokens that vanished without an attribution marker in `after`."""
    before_set = tokens(before)
    after_set = tokens(after)
    vanished: list[str] = []
    before_counts: dict[str, int] = {}
    after_counts: dict[str, int] = {}
    for t in before_set:
        before_counts[t] = before_counts.get(t, 0) + 1
    for t in after_set:
        after_counts[t] = after_counts.get(t, 0) + 1
    for token, count in before_counts.items():
        if after_counts.get(token, 0) < count:
            vanished.append(token)
    if not vanished:
        return []
    attributed = bool(ATTR_RE.search(after))
    if attributed:
        return []
    return [{"token": t, "reason": "unattributed-id-change"} for t in vanished]


def silent_rewrites_path(before: Path, after: Path) -> list[dict[str, str]]:
    return silent_rewrites(
        before.read_text(encoding="utf-8"), after.read_text(encoding="utf-8")
    )
