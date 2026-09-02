"""Plant a scratch tree with Windows reserved device names plus a known-present file."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from enumerator import (
    KNOWN_PRESENT_NAME,
    KNOWN_PRESENT_PAYLOAD,
    RESERVED_BASENAMES,
)

NESTED_DIR = "nested"
NESTED_ORDINARY = "also-ordinary.txt"


def hostile_root(here: Path) -> Path:
    return here / "runtime" / "hostile-tree"


def ordinary_root(here: Path) -> Path:
    return here / "runtime" / "ordinary-tree"


def wipe(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)


def plant_hostile(here: Path) -> dict[str, Any]:
    """Reserved names + known-present ordinary file + one nested ordinary file."""
    root = hostile_root(here)
    wipe(root)
    root.mkdir(parents=True, exist_ok=True)
    nested = root / NESTED_DIR
    nested.mkdir()
    planted: list[str] = []
    (root / KNOWN_PRESENT_NAME).write_text(KNOWN_PRESENT_PAYLOAD, encoding="utf-8")
    planted.append(KNOWN_PRESENT_NAME)
    (nested / NESTED_ORDINARY).write_text("nested-ordinary\n", encoding="utf-8")
    planted.append(f"{NESTED_DIR}/{NESTED_ORDINARY}")
    reserved_rels: list[str] = []
    for name in RESERVED_BASENAMES:
        path = root / name
        path.write_text(f"reserved:{name}\n", encoding="utf-8")
        if not path.is_file():
            raise RuntimeError(f"failed to plant reserved file {name}")
        planted.append(name)
        reserved_rels.append(name)
    expected = sorted(planted)
    return {
        "root": str(root),
        "planted": expected,
        "planted_count": len(expected),
        "reserved_rels": sorted(reserved_rels),
        "known_present": KNOWN_PRESENT_NAME,
        "nested_ordinary": f"{NESTED_DIR}/{NESTED_ORDINARY}",
    }


def plant_ordinary(here: Path) -> dict[str, Any]:
    """Negative control: same shape, no reserved names."""
    root = ordinary_root(here)
    wipe(root)
    root.mkdir(parents=True, exist_ok=True)
    nested = root / NESTED_DIR
    nested.mkdir()
    (root / KNOWN_PRESENT_NAME).write_text(KNOWN_PRESENT_PAYLOAD, encoding="utf-8")
    (nested / NESTED_ORDINARY).write_text("nested-ordinary\n", encoding="utf-8")
    planted = [KNOWN_PRESENT_NAME, f"{NESTED_DIR}/{NESTED_ORDINARY}"]
    return {
        "root": str(root),
        "planted": sorted(planted),
        "planted_count": len(planted),
        "reserved_rels": [],
        "known_present": KNOWN_PRESENT_NAME,
    }
