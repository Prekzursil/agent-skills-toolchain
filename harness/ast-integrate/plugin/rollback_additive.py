"""Additive rollback: restore managed bytes, never delete extras."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


class RollbackDestroyedProtected(RuntimeError):
    def __init__(self, message: str, report: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.report = report or {}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _paths(root: Path, sub: str) -> list[str]:
    base = Path(root) / sub
    if not base.exists():
        return []
    out = []
    for p in base.rglob("*"):
        if p.is_file():
            out.append(p.relative_to(root).as_posix())
    return sorted(out)


def rollback(
    profile: Path,
    backup: Path,
    mode: str = "additive",
    raise_on_loss: bool = False,
) -> dict[str, Any]:
    profile = Path(profile)
    backup = Path(backup)
    before_cmds = _paths(profile, "commands")
    before_ud = _paths(profile, "user-data")
    if mode != "additive":
        raise ValueError(f"unsupported rollback mode {mode}")
    for src in backup.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(backup)
        dest = profile / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
    after_cmds = _paths(profile, "commands")
    after_ud = _paths(profile, "user-data")
    cmd_diff = sorted(set(before_cmds) - set(after_cmds))
    ud_diff = sorted(set(before_ud) - set(after_ud))
    report = {
        "mode": mode,
        "before": {"command_paths": before_cmds, "user_data_paths": before_ud},
        "after": {"command_paths": after_cmds, "user_data_paths": after_ud},
        "set_difference": {
            "commands_present_before_absent_after": cmd_diff,
            "user_data_present_before_absent_after": ud_diff,
            "empty": not cmd_diff and not ud_diff,
        },
        "executed": True,
        "rehearsal_executed": True,
    }
    if raise_on_loss and (cmd_diff or ud_diff):
        raise RollbackDestroyedProtected("protected path lost", report)
    return report
