"""Census of program-state control planes (IMP-0450)."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

PROGRAM_LEDGER_PLANE_ID = "command-center-program-ledger"


@dataclass
class Introduced:
    kind: str
    name: str
    path: str = ""


@dataclass
class Census:
    control_plane_count: int
    existing_plane_id: str = PROGRAM_LEDGER_PLANE_ID
    introduced: list[Introduced] = field(default_factory=list)
    scanned_files: int = 0

    @property
    def is_single_plane(self) -> bool:
        return self.control_plane_count == 1

    @property
    def introduced_count(self) -> int:
        return len(self.introduced)

    def as_dict(self) -> dict[str, Any]:
        return {
            "control_plane_count": self.control_plane_count,
            "existing_plane_id": self.existing_plane_id,
            "introduced_count": self.introduced_count,
            "introduced": [i.__dict__ for i in self.introduced],
            "scanned_files": self.scanned_files,
            "is_single_plane": self.is_single_plane,
        }


def census_program_planes(
    roots: Iterable[Path] | Path | None = None,
    repo_root: Path | None = None,
    extra_files: list[Path] | None = None,
) -> Census:
    if roots is None:
        roots = []
    if isinstance(roots, (str, Path)):
        roots = [Path(roots)]
    files: list[Path] = []
    for root in roots:
        root = Path(root)
        if root.is_file():
            files.append(root)
            continue
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            files.append(path)
    for path in extra_files or []:
        files.append(Path(path))
    introduced: list[Introduced] = []
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and (
                "Dispatcher" in node.name or node.name.endswith("Dispatcher")
            ):
                introduced.append(
                    Introduced(kind="dispatcher-class", name=node.name, path=str(path))
                )
    count = 1 + len(introduced)
    return Census(
        control_plane_count=count,
        existing_plane_id=PROGRAM_LEDGER_PLANE_ID,
        introduced=introduced,
        scanned_files=len(files),
    )


__all__ = ["Census", "PROGRAM_LEDGER_PLANE_ID", "census_program_planes"]
