"""Install handoff document helpers. Digest only; no signing/verification API."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def load_handoff(path: Path) -> dict[str, Any]:
    import json

    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest_of(handoff: dict[str, Any]) -> str:
    d = handoff.get("digest")
    if isinstance(d, dict):
        return str(d.get("value") or "")
    return str(d or "")
