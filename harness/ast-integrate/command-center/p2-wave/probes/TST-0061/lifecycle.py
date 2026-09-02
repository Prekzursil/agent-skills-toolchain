"""Plugin lifecycle replace: naive sequential vs locked-aware refuse-or-swap.

Naive in-place overwrite is the P0: unlocked files become N, the held file
stays N-1, the command may then raise, and the tree is mixed even if later
steps fail.

Locked-aware preflights every path the command would mutate. If any path is
held it refuses, naming pid= and the process name, and writes nothing.
If none are held it stages a sibling tree and swaps by directory rename.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from inventory import compare, inventory
from scenario import FILE_ORDER, V1, V2, payload
from winlock import LockedFilesError, SharingViolation, WinLockFS


def _targets(root: Path, command: str) -> list[Path]:
    return [root / rel for rel in FILE_ORDER]


def preflight(fs: WinLockFS, root: Path, command: str) -> None:
    held = []
    for path in _targets(root, command):
        locker = fs.locker_for(path)
        if locker is not None:
            held.append((path.relative_to(root).as_posix(), locker))
    if held:
        raise LockedFilesError(command, held)


def naive_replace(fs: WinLockFS, root: Path, version: str) -> dict[str, Any]:
    """In-place sequential overwrite. Mixes versions when a later file is held."""
    wrote: list[str] = []
    new = payload(version)
    try:
        for rel in FILE_ORDER:
            fs.write_bytes(root / rel, new[rel])
            wrote.append(rel)
    except SharingViolation as exc:
        return {
            "ok": False,
            "strategy": "naive-inplace",
            "wrote": wrote,
            "failed_path": Path(exc.filename).as_posix(),
            "error": str(exc),
            "winerror": exc.winerror,
            "locker_pid": exc.locker.pid,
            "locker_name": exc.locker.name,
        }
    return {
        "ok": True,
        "strategy": "naive-inplace",
        "wrote": wrote,
        "failed_path": None,
        "error": None,
    }


def naive_uninstall(fs: WinLockFS, root: Path) -> dict[str, Any]:
    removed: list[str] = []
    try:
        for rel in FILE_ORDER:
            path = root / rel
            if path.exists():
                fs.unlink(path)
                removed.append(rel)
    except SharingViolation as exc:
        return {
            "ok": False,
            "strategy": "naive-unlink",
            "removed": removed,
            "error": str(exc),
            "winerror": exc.winerror,
            "locker_pid": exc.locker.pid,
            "locker_name": exc.locker.name,
        }
    return {"ok": True, "strategy": "naive-unlink", "removed": removed, "error": None}


def locked_aware(
    fs: WinLockFS,
    root: Path,
    command: str,
    *,
    new_version: str | None = None,
) -> dict[str, Any]:
    """Refuse naming the locker, or complete via staging + directory swap."""
    pre = inventory(root)
    try:
        preflight(fs, root, command)
    except LockedFilesError as exc:
        post = inventory(root)
        return {
            "ok": False,
            "refused": True,
            "strategy": "preflight-refuse",
            "command": command,
            "error": exc.message,
            "named_pids": [locker.pid for _, locker in exc.held],
            "named_names": [locker.name for _, locker in exc.held],
            "held": [
                {
                    "path": rel,
                    "pid": locker.pid,
                    "name": locker.name,
                    "kind": locker.kind,
                }
                for rel, locker in exc.held
            ],
            "tree_unchanged": compare(pre, post)["identical"],
            "compare": compare(pre, post),
        }

    parent = root.parent
    token = command
    staging = parent / f".{root.name}.staging-{token}"
    backup = parent / f".{root.name}.backup-{token}"
    if staging.exists():
        for p in sorted(staging.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
        if staging.exists():
            staging.rmdir()

    if command == "uninstall":
        if backup.exists():
            raise FileExistsError(str(backup))
        fs.rename_dir(root, backup)
        return {
            "ok": True,
            "refused": False,
            "strategy": "rename-aside",
            "command": command,
            "error": None,
            "backup": backup.as_posix(),
        }

    version = new_version or (V2 if command == "update" else V1)
    staging.mkdir(parents=True, exist_ok=True)
    for rel, data in payload(version).items():
        dest = staging / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    if backup.exists():
        raise FileExistsError(str(backup))
    fs.rename_dir(root, backup)
    fs.rename_dir(staging, root)
    try:
        for p in sorted(backup.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
        if backup.exists():
            backup.rmdir()
    except OSError:
        pass
    return {
        "ok": True,
        "refused": False,
        "strategy": "stage-then-rename",
        "command": command,
        "error": None,
        "version": version,
    }


def rename_then_write_update(fs: WinLockFS, root: Path) -> dict[str, Any]:
    """Atomic-complete alternative: rename held dest aside, write the new file.

    Canonical install paths then all carry N. Pending-reboot leftovers are
    sibling *.pending-reboot files, not a mixed plugin tree.
    """
    pending: list[str] = []
    new = payload(V2)
    try:
        for rel in FILE_ORDER:
            dest = root / rel
            if dest.exists() and fs.is_held(dest):
                aside = dest.with_name(dest.name + ".pending-reboot")
                fs.rename_file(dest, aside)
                pending.append(aside.name)
            fs.write_bytes(dest, new[rel])
    except SharingViolation as exc:
        return {
            "ok": False,
            "strategy": "rename-then-write",
            "error": str(exc),
            "pending_reboot": pending,
        }
    return {
        "ok": True,
        "strategy": "rename-then-write",
        "pending_reboot": pending,
        "error": None,
    }
