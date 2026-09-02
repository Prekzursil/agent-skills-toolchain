"""A2 deploy installer used on this worktree (ARC-0014 freeze_hook.deploy_write)."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ARC-0014"))
from freeze_hook import deploy_write as a2_deploy_write  # noqa: E402


def install_files(root: Path, files: dict[str, bytes]) -> list[str]:
    """Write each relative path through the live A2 installer. Order is insertion order."""
    written: list[str] = []
    for rel, data in files.items():
        dest = a2_deploy_write(root, rel, data)
        written.append(dest.name)
    return written
