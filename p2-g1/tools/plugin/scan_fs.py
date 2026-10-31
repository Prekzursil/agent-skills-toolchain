"""Walk a payload tree and yield (posix-rel, text) for secret scanners."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator


def iter_text_files(root: Path) -> Iterator[tuple[str, str]]:
    root = Path(root)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "__pycache__"}]
        for name in filenames:
            path = Path(dirpath) / name
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            yield rel, text
