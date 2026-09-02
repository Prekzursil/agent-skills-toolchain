"""Load the planted registry and goals. Fixture ids live here, not in the guard."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from workflow_foundry.anti_rebuild_guard import Registry, load_registry  # noqa: E402

FIX = HERE / "fixtures"
PLANTED_ID = "wf.planted.incumbent.scout"
INFERIOR_ID = "wf.inferior.license.rollback"
INCOMPARABLE_ID = "wf.incomparable.legacy-etl"
PLANTED_RUN = "bench-2026-08-01-alpha-scout"


def registry() -> Registry:
    return load_registry(FIX / "registry.json")


def goals() -> dict:
    return json.loads((FIX / "goals.json").read_text(encoding="utf-8"))
