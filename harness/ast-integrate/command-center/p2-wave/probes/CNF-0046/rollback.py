"""Rollback under three lock-handling modes.

aware        — preflight: if any target is locked, refuse the whole tree,
               name the locker, write nothing. This is the implementation
               under test (Windows sharing-violation analogue on Linux).
naive-skip   — on lock, skip that file and continue. Detector control for
               silent-skip mixed version.
posix-replace — os.replace with no lock check. POSIX native: replace
               succeeds while a fd is held; the locker keeps the old inode.
"""
from __future__ import annotations

import fcntl
import os
from pathlib import Path
from typing import Any

from handles import comm_of, flock_pids_from_proc_locks, list_lockers
from inventory import corrupted, mixed_version, walk
from scenario import FILES

EXIT_REFUSED = 2
EXIT_OK = 0
EXIT_MIXED = 1


def _try_exclusive(path: Path) -> tuple[int | None, str]:
    try:
        fd = os.open(path, os.O_RDWR)
    except OSError as exc:
        return None, f"open-failed:{exc.__class__.__name__}:{exc}"
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None, "sharing-violation:fcntl.LOCK_EX|LOCK_NB BlockingIOError"
    except OSError as exc:
        os.close(fd)
        return None, f"flock-failed:{exc.__class__.__name__}:{exc}"
    return fd, ""


def _close_fds(fds: list[int]) -> None:
    for fd in fds:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(fd)
        except OSError:
            pass


def _replace(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".rollback-tmp")
    tmp.write_bytes(src.read_bytes())
    os.replace(tmp, dest)


def _format_error(blocked: list[dict[str, Any]]) -> str:
    lines = [
        "ROLLBACK REFUSED: target files are locked by another process.",
    ]
    for row in blocked:
        rel = row["path"]
        for h in row.get("handle_list") or []:
            lines.append(
                f"  {rel}: pid={h.get('pid')} comm={h.get('comm') or '?'} "
                f"fd={h.get('fd')} (inode {h.get('ino')})"
            )
        if not row.get("handle_list"):
            lines.append(f"  {rel}: {row.get('reason')}")
    lines.append(
        "Unlock the named process and retry; a partial rollback was not applied."
    )
    return "\n".join(lines)


def rollback(prefix: Path, snapshot: Path, mode: str = "aware") -> dict[str, Any]:
    rels = list(FILES.keys())
    pre = walk(prefix)
    blocked: list[dict[str, Any]] = []
    skipped: list[str] = []
    held: list[int] = []
    handle_list: list[dict[str, Any]] = []

    for rel in rels:
        dest = prefix / rel
        lockers = list_lockers(dest)
        flock_pids = flock_pids_from_proc_locks(dest)
        if mode == "posix-replace":
            handle_list.extend(lockers)
            continue
        fd, reason = _try_exclusive(dest) if dest.is_file() else (None, "missing")
        locked = fd is None or bool(lockers)
        row = {
            "path": rel,
            "reason": reason,
            "handle_list": lockers,
            "flock_pids": flock_pids,
        }
        if locked:
            if not lockers:
                for pid in flock_pids:
                    lockers.append(
                        {
                            "pid": pid,
                            "comm": comm_of(pid),
                            "fd": "proc-locks",
                            "path": dest.as_posix(),
                            "ino": None,
                        }
                    )
                row["handle_list"] = lockers
            if mode == "aware":
                blocked.append(row)
                handle_list.extend(lockers)
            else:
                skipped.append(rel)
                handle_list.extend(lockers)
        elif fd is not None:
            held.append(fd)

    if mode == "aware" and blocked:
        _close_fds(held)
        post = walk(prefix)
        err = _format_error(blocked)
        locking = handle_list[0] if handle_list else {}
        return {
            "mode": mode,
            "exit_code": EXIT_REFUSED,
            "error_text": err,
            "wrote": False,
            "skipped": [],
            "blocked_paths": [b["path"] for b in blocked],
            "handle_list": handle_list,
            "locking_process": {
                "pid": locking.get("pid"),
                "comm": locking.get("comm"),
            },
            "pre": pre,
            "post": post,
            "mixed_version": mixed_version(post),
            "corrupted": corrupted(post),
            "names_locking_process": bool(locking.get("pid")),
        }

    wrote: list[str] = []
    to_write = [rel for rel in rels if rel not in skipped]
    _close_fds(held)
    held = []
    for rel in to_write:
        _replace(snapshot / rel, prefix / rel)
        wrote.append(rel)

    post = walk(prefix)
    is_mixed = mixed_version(post)
    exit_code = EXIT_OK
    error_text = ""
    if mode == "naive-skip" and skipped:
        error_text = ""
        exit_code = EXIT_OK if not is_mixed else EXIT_OK
    if is_mixed:
        exit_code = EXIT_OK if mode == "naive-skip" else EXIT_MIXED
    locking = handle_list[0] if handle_list else {}
    return {
        "mode": mode,
        "exit_code": exit_code,
        "error_text": error_text,
        "wrote": True,
        "wrote_paths": wrote,
        "skipped": skipped,
        "blocked_paths": [],
        "handle_list": handle_list,
        "locking_process": {
            "pid": locking.get("pid"),
            "comm": locking.get("comm"),
        },
        "pre": pre,
        "post": post,
        "mixed_version": is_mixed,
        "corrupted": corrupted(post),
        "names_locking_process": bool(locking.get("pid")) if handle_list else False,
    }
