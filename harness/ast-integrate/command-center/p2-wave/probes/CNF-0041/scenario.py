"""Disposable fixture: affected trees, reserved NUL, and a mutating change."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST_REL = "fixtures/ROLLBACK-MANIFEST.md"
RESERVED_REL = "affected/app/NUL"
PLANTED_REL = "affected/app/PLANTED-CNF-0041.residue"
MAIN_REL = "affected/app/main.py"
KEEP_REL = "affected/config/keep.txt"
NEW_REL = "affected/app/new_module.py"

MAIN_PRE = b"print('pre-state main')\n# CNF-0041 fixture\n"
MAIN_POST = b"print('POST-CHANGE main')\n# mutated\n"
KEEP_PRE = b"keep-me-across-rollback\n"
SETTINGS_PRE = b'{"theme": "dark", "version": 1}\n'
NUL_PRE = b"reserved-device-name-payload\n"


def manifest_path() -> Path:
    return HERE / MANIFEST_REL


def build_pre_state(root: Path) -> None:
    app = root / "affected" / "app"
    cfg = root / "affected" / "config"
    app.mkdir(parents=True, exist_ok=True)
    cfg.mkdir(parents=True, exist_ok=True)
    (root / MAIN_REL).write_bytes(MAIN_PRE)
    (root / KEEP_REL).write_bytes(KEEP_PRE)
    (root / "affected/config/settings.json").write_bytes(SETTINGS_PRE)
    (root / RESERVED_REL).write_bytes(NUL_PRE)


def apply_change(root: Path) -> None:
    (root / MAIN_REL).write_bytes(MAIN_POST)
    keep = root / KEEP_REL
    if keep.is_file():
        keep.unlink()
    (root / NEW_REL).write_bytes(b"added during change; complete rollback must drop this\n")


def plant_residue(root: Path) -> str:
    dest = root / PLANTED_REL
    dest.write_bytes(b"planted-before-rollback detector control\n")
    return PLANTED_REL
