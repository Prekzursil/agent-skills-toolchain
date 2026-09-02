"""Load work-unit records from the merged catalog (CC-0008 output)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"


def load_units() -> list[dict[str, Any]]:
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = doc.get("work_units") or []
    if not isinstance(units, list) or not units:
        raise SystemExit("FAILED:CC-0020 catalog work_units empty")
    return units


def by_id() -> dict[str, dict[str, Any]]:
    return {u["id"]: u for u in load_units() if isinstance(u, dict) and "id" in u}
