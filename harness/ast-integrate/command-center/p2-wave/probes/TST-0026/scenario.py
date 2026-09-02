#!/usr/bin/env python3
"""Copy the fixture freeze tree into a scratch directory."""
from __future__ import annotations

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE / "fixtures" / "tree"


def copy_tree(dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(TREE, dest)
    return dest
