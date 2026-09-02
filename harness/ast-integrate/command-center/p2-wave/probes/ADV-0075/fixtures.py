"""Adversarial filename fixture tree for ADV-0075.

Names are the payload. Contents are unique beacons so a wrong open is visible.
The tree is created at probe time; newline and leading-dash names are not
committed as git paths.
"""
from __future__ import annotations

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE / "fixture-tree"

RTL_OVERRIDE = "\u202e"
CYRILLIC_O = "\u043e"

ORDINARY = "ordinary.txt"
LATIN_CONFIG = "config.json"
HOMOGLYPH_CONFIG = f"c{CYRILLIC_O}nfig.json"
RTL_NAME = f"pic{RTL_OVERRIDE}gpj.exe"
NEWLINE_NAME = "note.txt\nextra.dat"
DASH_NAME = "-n"
CASE_LOWER = "control.txt"
CASE_UPPER = "CONTROL.txt"

PAYLOADS = {
    ORDINARY: "ADV-0075-CONTROL-ORDINARY\n",
    LATIN_CONFIG: '{"role":"latin-config"}\n',
    HOMOGLYPH_CONFIG: '{"role":"homoglyph-twin"}\n',
    RTL_NAME: "ADV-0075-RTL-PAYLOAD\n",
    NEWLINE_NAME: "ADV-0075-NEWLINE-PAYLOAD\n",
    DASH_NAME: "ADV-0075-DASH-PAYLOAD\n",
    CASE_LOWER: "ADV-0075-CASE-LOWER\n",
    CASE_UPPER: "ADV-0075-CASE-UPPER\n",
}

ALL_NAMES = (
    ORDINARY,
    LATIN_CONFIG,
    HOMOGLYPH_CONFIG,
    RTL_NAME,
    NEWLINE_NAME,
    DASH_NAME,
    CASE_LOWER,
    CASE_UPPER,
)


def hex_name(name: str) -> str:
    return name.encode("utf-8").hex()


def ensure_tree() -> Path:
    if TREE.exists():
        shutil.rmtree(TREE)
    TREE.mkdir(parents=True)
    for name, body in PAYLOADS.items():
        path = TREE / name
        path.write_text(body, encoding="utf-8")
    return TREE


ensure_tree = ensure_tree


def true_names(tree: Path | None = None) -> list[str]:
    root = tree or TREE
    return sorted(p.name for p in root.iterdir() if p.is_file())
