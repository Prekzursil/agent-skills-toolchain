"""Gated security-blueprint contract: four registered workflows, one flagship."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def register(lib: Path | None = None) -> dict[str, Any]:
    root = Path(lib) if lib is not None else HERE
    registry_path = root / "registry.json"
    doc = json.loads(registry_path.read_text(encoding="utf-8"))
    rows = [b for b in (doc.get("blueprints") or []) if isinstance(b, dict)]
    registered = [str(b.get("id") or "") for b in rows if b.get("id")]
    flagship = [str(x) for x in (doc.get("flagship") or [])]
    if not flagship:
        flagship = [str(b.get("id")) for b in rows if b.get("flagship")]
    missing = [
        str(b.get("module"))
        for b in rows
        if b.get("module") and not (root / str(b["module"])).is_file()
    ]
    ok = len(registered) == 4 and bool(flagship) and not missing
    return {
        "pass": ok,
        "registered": registered,
        "flagship": flagship,
        "missing_modules": missing,
        "registry": str(registry_path).replace("\\", "/"),
    }
