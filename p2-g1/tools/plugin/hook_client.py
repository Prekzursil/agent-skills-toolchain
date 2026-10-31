"""Hook inventory client: the SECOND signal for the hook-fire probe (IMP-0039).

The hook script writes a sentinel after a real trigger; the client reads the
hooks.json and reports which hooks the config actually loads. Any top-level key
outside {hooks} (e.g. a Codex-shaped `$schema`) means the client loads ZERO
hooks — the recorded zero-load precedent this unit exists to catch.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

KNOWN_TOP_LEVEL_KEYS = {"hooks"}


def load_inventory(config_dir: Path | str) -> dict[str, Any]:
    root = Path(config_dir)
    hooks_path = root / "hooks.json"
    try:
        doc = json.loads(hooks_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "loaded": [],
            "reason": f"unreadable:{type(exc).__name__}",
            "extra_keys": [],
            "config": str(hooks_path),
        }
    if not isinstance(doc, dict):
        return {"loaded": [], "reason": "not-an-object", "extra_keys": [],
                "config": str(hooks_path)}
    extra = [k for k in doc.keys() if k not in KNOWN_TOP_LEVEL_KEYS]
    loaded: list[str] = []
    if extra:
        return {
            "loaded": [],
            "reason": "unknown-top-level-keys",
            "extra_keys": extra,
            "config": str(hooks_path),
        }
    for _event, entries in (doc.get("hooks") or {}).items():
        for entry in entries or []:
            loaded.append(str(entry.get("id") or "hook.pre-tool"))
    return {"loaded": loaded, "reason": "ok", "extra_keys": [], "config": str(hooks_path)}


def client_document(config_dir: Path | str) -> dict[str, Any]:
    """The full client-side inventory document (probe's second signal)."""
    return load_inventory(config_dir)


__all__ = ["KNOWN_TOP_LEVEL_KEYS", "client_document", "load_inventory"]
