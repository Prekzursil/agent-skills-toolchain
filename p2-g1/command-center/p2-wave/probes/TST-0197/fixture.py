"""Planted tree builder for TST-0197 (reserved device names + ordinary files)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

RESERVED_NAMES = ["NUL", "CON", "AUX", "PRN", "COM1", "LPT1"]
ORDINARY_NAMES = ["readme.md", "alpha.txt", "beta.txt", "notes.txt"]


def plant_tree(root: Path | None = None) -> Path:
    """Create a tree of 8 files including the six reserved basenames.

    On Windows the reserved names are created through the extended-length
    \?\ prefix when the plain Win32 form refuses; on POSIX they are plain.
    """
    root = Path(root) if root else Path(tempfile.mkdtemp(prefix="tst0197-"))
    (root / "sub").mkdir(parents=True, exist_ok=True)
    targets = (
        [(root, n) for n in ORDINARY_NAMES[:2]]
        + [(root / "sub", n) for n in RESERVED_NAMES]
        + [(root / "sub", ORDINARY_NAMES[2])]
        + [(root, ORDINARY_NAMES[3])]
    )
    planted: list[str] = []
    skipped: list[str] = []
    for directory, name in targets:
        directory.mkdir(parents=True, exist_ok=True)
        dest = directory / name
        payload = f"tst-0197 fixture: {name}\n".encode("utf-8")
        written = False
        try:
            dest.write_bytes(payload)
            written = True
        except OSError:
            if os.name == "nt":
                try:
                    with open("\\?\\" + str(dest.resolve()), "wb") as fh:
                        fh.write(payload)
                    written = True
                except OSError:
                    written = False
        (planted if written else skipped).append(name)
    root.joinpath("_plant_report.json").write_text(
        __import__("json").dumps({"planted": sorted(planted), "skipped": sorted(skipped)}, indent=1),
        encoding="utf-8",
    )
    return root
