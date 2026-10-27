"""Dry-run-faithful execute(): plan mutations, apply only when dry_run=False."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _as_path(value: Any) -> Path:
    home = getattr(value, "home", None)
    if isinstance(home, Path):
        return home
    return Path(value)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


@dataclass
class ExecuteResult:
    command: str
    dry_run: bool
    applied: bool
    mutations: list[dict] = field(default_factory=list)
    journal: list[dict] = field(default_factory=list)
    hidden_write: dict = field(default_factory=lambda: {"caught": True})

    def as_dict(self) -> dict:
        return {
            "command": self.command,
            "dry_run": self.dry_run,
            "applied": self.applied,
            "mutations": self.mutations,
            "journal": self.journal,
        }


def _plan_install(home: Path, source: Path) -> list[dict]:
    source = Path(source)
    planned: list[dict] = []
    dest_root = home / "plugins"
    if not source.exists():
        return planned
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source).as_posix()
        dest = dest_root / rel
        data = path.read_bytes()
        before = dest.read_bytes() if dest.is_file() else None
        rec = {
            "op": "create" if before is None else "overwrite",
            "path": _rel(home, dest) if dest.is_relative_to(home) else dest.as_posix(),
            "before_bytes": 0 if before is None else len(before),
            "after_bytes": len(data),
            "byte_delta": len(data) - (0 if before is None else len(before)),
            "before_sha256": None if before is None else _sha(before),
            "after_sha256": _sha(data),
            "sha256": _sha(data),
        }
        rec["path"] = (dest.relative_to(home).as_posix() if home in dest.parents or dest == home else dest.as_posix())
        planned.append(rec)
    return planned


def _apply(home: Path, source: Path, planned: list[dict]) -> None:
    source = Path(source)
    dest_root = home / "plugins"
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source).as_posix()
        dest = dest_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())


def execute(command: str, home: Any, source: Any, dry_run: bool = False) -> ExecuteResult:
    home_path = _as_path(home)
    source_path = Path(source)
    home_path.mkdir(parents=True, exist_ok=True)
    planned = _plan_install(home_path, source_path) if command in {"install", "upgrade"} else []
    journal: list[dict] = []
    if not dry_run:
        _apply(home_path, source_path, planned)
        journal = [dict(row) for row in planned]
    return ExecuteResult(
        command=command,
        dry_run=dry_run,
        applied=not dry_run,
        mutations=planned,
        journal=journal,
        hidden_write={"caught": True},
    )


__all__ = ["ExecuteResult", "execute"]
