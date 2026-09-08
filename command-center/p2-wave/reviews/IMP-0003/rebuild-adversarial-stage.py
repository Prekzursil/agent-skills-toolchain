#!/usr/bin/env python3
"""Rebuild the independent-review novel plant staging tree (nested gitlink FILE)."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent / "adversarial-stage"
plant = ROOT / "vendor" / "plugin-sub" / ".git"
plant.parent.mkdir(parents=True, exist_ok=True)
plant.write_text("gitdir: ../../../.git/modules/plugin-sub\n", encoding="utf-8")
(ROOT / "README.md").write_text("# legitimate\n", encoding="utf-8")
print(f"rebuilt {plant} is_file={plant.is_file()}")
