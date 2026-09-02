"""Load two real catalog units used as the differential sample on every rail."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SAMPLE_IDS = ("IMP-0421", "IMP-0422")


def load_catalog_unit(repo: Path, uid: str) -> dict[str, Any]:
    data = json.loads(
        (repo / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == uid:
            return unit
    raise KeyError(f"catalog missing {uid}")


def sample_units(repo: Path) -> list[dict[str, Any]]:
    return [load_catalog_unit(repo, uid) for uid in SAMPLE_IDS]
