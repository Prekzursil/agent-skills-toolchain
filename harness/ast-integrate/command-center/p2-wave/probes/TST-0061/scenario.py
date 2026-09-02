"""Disposable plugin tree: hook, active log, interpreter module, plus extras."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from inventory import inventory
from winlock import Locker, WinLockFS

V1 = "1.0.0"
V2 = "2.0.0"

# Unlocked files first so a naive sequential replace mixes versions when
# it later hits the held hook / log / module.
FILE_ORDER = (
    "plugin.json",
    "skills/SKILL.md",
    "rules/rule.md",
    "hooks/on_load.py",
    "logs/plugin.log",
    "lib/runtime.py",
)

LOCKERS = {
    "hooks/on_load.py": Locker(pid=4242, name="claude-hooks.exe", kind="hook"),
    "logs/plugin.log": Locker(pid=4243, name="plugin-host.exe", kind="log"),
    "lib/runtime.py": Locker(pid=8811, name="python.exe", kind="module"),
}


def _body(rel: str, version: str) -> bytes:
    marker = f"TST0061_VERSION={version}"
    if rel == "plugin.json":
        return (
            '{\n'
            f'  "name": "tst-0061-fixture",\n'
            f'  "version": "{version}"\n'
            "}\n"
        ).encode("utf-8")
    if rel == "hooks/on_load.py":
        return f"# loaded hook script\n{marker}\nHOOK = {version!r}\n".encode("utf-8")
    if rel == "logs/plugin.log":
        return f"# active log (handle held by host)\n{marker}\n".encode("utf-8")
    if rel == "lib/runtime.py":
        return (
            f"# running interpreter's own module\n{marker}\n"
            f"RUNTIME = {version!r}\n"
        ).encode("utf-8")
    if rel == "skills/SKILL.md":
        return f"# skill\n{marker}\n".encode("utf-8")
    if rel == "rules/rule.md":
        return f"# rule\n{marker}\n".encode("utf-8")
    raise KeyError(rel)


def payload(version: str) -> dict[str, bytes]:
    return {rel: _body(rel, version) for rel in FILE_ORDER}


def seed(root: Path, version: str = V1) -> list[dict[str, Any]]:
    root.mkdir(parents=True, exist_ok=True)
    for rel, data in payload(version).items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return inventory(root)


def hold_kind(fs: WinLockFS, root: Path, kind: str) -> Locker:
    for rel, locker in LOCKERS.items():
        if locker.kind == kind:
            fs.hold(root / rel, locker)
            return locker
    raise KeyError(kind)


def hold_all_lifecycle_files(fs: WinLockFS, root: Path) -> list[Locker]:
    held: list[Locker] = []
    for rel, locker in LOCKERS.items():
        fs.hold(root / rel, locker)
        held.append(locker)
    return held
