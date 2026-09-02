"""Drop cwd/repo from sys.path so stdlib platform is not shadowed."""
from __future__ import annotations

import sys
from pathlib import Path


def unshadow() -> None:
    cwd = Path.cwd().resolve()
    drop = {"", ".", str(cwd), str(Path.cwd())}
    cleaned: list[str] = []
    for p in sys.path:
        if p in drop:
            continue
        if p:
            root = Path(p)
            if (root / "platform" / "__init__.py").is_file() and (
                root / "command-center"
            ).is_dir():
                continue
        cleaned.append(p)
    sys.path[:] = cleaned
    sys.modules.pop("platform", None)
