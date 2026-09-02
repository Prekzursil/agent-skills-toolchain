#!/usr/bin/env python3
"""Load CNL-0058 fixtures from disk."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    path = FIX / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def fixture_path(name: str) -> Path:
    return FIX / f"{name}.json"
