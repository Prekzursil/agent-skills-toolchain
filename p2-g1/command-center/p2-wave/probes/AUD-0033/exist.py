"""Existence tester with isolated path-length / encoding retry."""
from __future__ import annotations

import errno
import os
from pathlib import Path
from typing import Any


def read_text_with_retry(path: Path) -> tuple[str | None, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8", errors="replace"), "utf8-replace-retry"
        except OSError as exc:
            return None, f"unreadable-after-retry:{type(exc).__name__}"
    except OSError as exc:
        # retry this single file in isolation
        try:
            return path.read_text(encoding="utf-8", errors="replace"), f"oserror-retry:{exc.errno}"
        except OSError as exc2:
            return None, f"unreadable:{type(exc2).__name__}:{getattr(exc2, 'errno', None)}"


def _stat_once(path: Path) -> tuple[bool, str | None, str]:
    try:
        if path.exists():
            if path.is_file() or path.is_dir() or path.is_symlink():
                return True, None, "present"
        return False, None, "missing"
    except OSError as exc:
        en = getattr(exc, "errno", None)
        if en in {errno.ENAMETOOLONG, errno.EINVAL}:
            return False, f"path-length:{en}", "path-length"
        return False, f"oserror:{en}", "oserror"


def resolve_candidate(token: str, repo: Path) -> Path:
    if token.startswith("~/"):
        return Path.home() / token[2:]
    if token.startswith("/") or (len(token) > 2 and token[1] == ":"):
        return Path(token)
    return repo / token


def exists_with_retry(token: str, repo: Path) -> dict[str, Any]:
    """Test existence; on path-length/encoding OSError, retry this token alone."""
    target = resolve_candidate(token, repo)
    present, err, kind = _stat_once(target)
    retried = False
    if err and kind == "path-length":
        retried = True
        present2, err2, kind2 = _stat_once(target)
        present, err, kind = present2, err2, kind2
    windows = bool(len(token) > 2 and token[1] == ":" and token[0].isalpha())
    reason = "present" if present else "missing"
    if (not present) and windows and os.name != "nt":
        reason = "windows-path-on-linux"
    if kind == "path-length":
        reason = "path-length"
    return {
        "path": token,
        "resolved": str(target),
        "exists": bool(present),
        "reason": reason,
        "error": err,
        "retried_isolated": retried,
        "is_absolute": token.startswith("/") or token.startswith("~/") or windows,
        "windows": windows,
    }
