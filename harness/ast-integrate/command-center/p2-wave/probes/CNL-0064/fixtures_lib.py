"""Load CNL-0064 fixtures from disk."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"


def load_all() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in sorted(FIX.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        rows[str(doc["id"])] = doc
    return rows


def councils() -> dict[str, dict[str, Any]]:
    return {k: v for k, v in load_all().items() if v.get("kind") == "council"}


def published_results() -> dict[str, dict[str, Any]]:
    return {k: v for k, v in load_all().items() if v.get("kind") == "published-result"}
