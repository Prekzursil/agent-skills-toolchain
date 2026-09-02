"""Handle enumeration: /proc fd inode scan plus /proc/locks flock rows."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def inode_key(path: Path) -> tuple[int, int] | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return int(st.st_dev), int(st.st_ino)


def comm_of(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/comm").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def list_lockers(path: Path, exclude_pids: set[int] | None = None) -> list[dict[str, Any]]:
    """Return processes that hold an open fd to ``path`` (same device+inode)."""
    want = inode_key(path)
    if want is None:
        return []
    exclude = set(exclude_pids or ())
    exclude.add(os.getpid())
    found: list[dict[str, Any]] = []
    proc = Path("/proc")
    try:
        entries = list(proc.iterdir())
    except OSError:
        return []
    for entry in entries:
        name = entry.name
        if not name.isdigit():
            continue
        pid = int(name)
        if pid in exclude:
            continue
        fd_dir = entry / "fd"
        try:
            fds = list(fd_dir.iterdir())
        except OSError:
            continue
        comm = comm_of(pid)
        for fd_path in fds:
            try:
                st = os.stat(fd_path)
            except OSError:
                continue
            if (int(st.st_dev), int(st.st_ino)) != want:
                continue
            found.append(
                {
                    "pid": pid,
                    "comm": comm,
                    "fd": fd_path.name,
                    "path": path.as_posix(),
                    "dev": want[0],
                    "ino": want[1],
                }
            )
    return found


def flock_pids_from_proc_locks(path: Path) -> list[int]:
    """PIDs with an advisory flock on this inode, from /proc/locks."""
    want = inode_key(path)
    if want is None:
        return []
    ino = want[1]
    pids: list[int] = []
    try:
        text = Path("/proc/locks").read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        # id: TYPE MODE KIND pid maj:min:inode start end
        parts = line.split()
        if len(parts) < 6:
            continue
        if parts[1] not in {"FLOCK", "POSIX"}:
            continue
        try:
            pid = int(parts[4])
        except ValueError:
            continue
        id_field = parts[5]
        if ":" not in id_field:
            continue
        inode_s = id_field.rsplit(":", 1)[-1]
        try:
            inode = int(inode_s)
        except ValueError:
            continue
        if inode == ino:
            pids.append(pid)
    return pids
