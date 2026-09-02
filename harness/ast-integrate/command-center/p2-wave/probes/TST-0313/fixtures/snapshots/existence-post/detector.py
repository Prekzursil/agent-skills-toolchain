"""Post-fix subject: empty, unparseable, or self-declared failure is not delivered."""
from __future__ import annotations

import json
from pathlib import Path

NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def is_delivered(path) -> bool:
    p = Path(path)
    if not p.is_file() or p.stat().st_size <= 0:
        return False
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(doc, dict):
        return False
    state = str(doc.get("state") or "").upper()
    if state in NOT_DELIVERING:
        return False
    return True
