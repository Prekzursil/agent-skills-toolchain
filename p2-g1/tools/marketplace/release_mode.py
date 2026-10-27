"""Release-mode constants for marketplace publishing (IMP-0112)."""
from __future__ import annotations

import json
from pathlib import Path

BINDING_MODE = "PR-ONLY"
PUBLIC_MODE = "PUBLIC_MARKETPLACE"


def load_mode(config_path: str | None = None) -> str:
    if not config_path:
        return BINDING_MODE
    path = Path(config_path)
    name = path.name.lower()
    if "pr-only" in name or "pr_only" in name:
        return BINDING_MODE
    if "public" in name:
        return PUBLIC_MODE
    if not path.is_file():
        return BINDING_MODE
    doc = json.loads(path.read_text(encoding="utf-8"))
    return str(doc.get("release_mode") or doc.get("mode") or BINDING_MODE)
