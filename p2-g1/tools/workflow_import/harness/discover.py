"""AST discovery of adapter IDs; planted-unregistered detector control."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from ..paths import ADAPTERS_DIR
from .registry import REGISTERED_ADAPTER_IDS


def discover_ids(directory: Path | None = None) -> list[str]:
    root = Path(directory) if directory else ADAPTERS_DIR
    found: list[str] = []
    if not root.is_dir():
        return found
    for path in sorted(root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if "ADAPTER_ID" in names and isinstance(node.value, ast.Constant):
                    found.append(str(node.value.value))
    return found


def assert_registry_closed() -> dict[str, Any]:
    discovered = discover_ids()
    unregistered = sorted(set(discovered) - set(REGISTERED_ADAPTER_IDS))
    return {
        "ok": not unregistered and set(discovered) == set(REGISTERED_ADAPTER_IDS),
        "discovered_ids": discovered,
        "unregistered": unregistered,
    }


def planted_unregistered_control() -> dict[str, Any]:
    live = assert_registry_closed()
    plant = ADAPTERS_DIR / "planted_unregistered.py"
    ADAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    plant.write_text('ADAPTER_ID = "planted-unregistered"\n', encoding="utf-8")
    try:
        planted_ids = discover_ids()
        fired = "planted-unregistered" in planted_ids
    finally:
        if plant.is_file():
            plant.unlink()
    restored = assert_registry_closed()
    return {
        "pass": bool(live["ok"] and fired and restored["ok"] and not plant.is_file()),
        "fired_on_plant": fired,
        "restored_closed": restored["ok"],
        "planted_ids": planted_ids,
        "live_closed": live["ok"],
    }
