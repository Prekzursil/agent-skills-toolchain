"""Fixture stand-in for hooks/_dispatch/test_wiring.py (absent at repo root)."""
from __future__ import annotations

import json
from pathlib import Path


def declared_hook_ids() -> list[str]:
    doc = json.loads(
        (Path(__file__).parent / "manifest.json").read_text(encoding="utf-8")
    )
    return list(doc["hooks"])
