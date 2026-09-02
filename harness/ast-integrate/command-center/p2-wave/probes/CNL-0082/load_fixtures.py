from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DIR = Path(__file__).resolve().parent / "fixtures"

NAMES = (
    "saturated-12.json",
    "unsaturated-12.json",
    "fatigue-repeat-queries.json",
    "time-arm-180.json",
    "near-identical-mirrors.json",
)


def load(name: str) -> dict[str, Any]:
    return json.loads((DIR / name).read_text(encoding="utf-8"))


def load_all() -> dict[str, dict[str, Any]]:
    return {n: load(n) for n in NAMES}
