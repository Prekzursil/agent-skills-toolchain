#!/usr/bin/env python3
r"""file-scope/_common.py — shared helpers for check.py and set_scope.py.

Pure stdlib. Every public helper is fail-soft (safe default) so callers stay
FAIL-OPEN. Self-contained: no cross-dir imports.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Directory resolution
# ---------------------------------------------------------------------------


def scopes_dir(hook_dir: Path) -> Path:
    """Return the scopes directory.

    Production:  <HOOK_DIR>/scopes/
    Test-isolation: FILE_SCOPE_DIR env overrides base to <FILE_SCOPE_DIR>/scopes/
    """
    base = os.environ.get("FILE_SCOPE_DIR", "")
    return Path(base) / "scopes" if base else hook_dir / "scopes"


# ---------------------------------------------------------------------------
# Filename helpers
# ---------------------------------------------------------------------------


def _safe(s: str) -> str:
    """Convert a string to a safe filesystem component (max 80 chars)."""
    return (
        "".join(c if c.isalnum() or c in "-_." else "-" for c in str(s))[:80]
        or "default"
    )


def _cwd_slug(cwd: str) -> str:
    """12-char sha1 slug of a normalized cwd path (case-folded)."""
    norm = cwd.replace("\\", "/").lower().rstrip("/")
    # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1 -- non-cryptographic cwd-path slug for a state key, not a security control
    return hashlib.sha1(norm.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]


def sidecar_path(sd: Path, key_type: str, key: str) -> Path:
    """Return the sidecar file path for a given key type + key."""
    if key_type == "session":
        return sd / f"session-{_safe(key)}.json"
    if key_type == "agent":
        return sd / f"agent-{_safe(key)}.json"
    if key_type == "cwd":
        return sd / f"cwd-{_cwd_slug(key)}.json"
    raise ValueError(f"unknown key_type: {key_type!r}")


# ---------------------------------------------------------------------------
# Sidecar I/O
# ---------------------------------------------------------------------------


def try_sidecar(path: Path) -> dict | None:
    """Load and validate a sidecar file.  Returns the dict or None.

    None means "no enforcement" — callers MUST exit 0 (fail-open) on None.
    None is returned for: missing file, bad JSON, wrong shape, expired TTL.
    A sidecar with an empty allow list IS valid — it blocks all writes.
    """
    try:
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8")
        if not raw.strip():
            return None
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            return None
        allow = obj.get("allow")
        if not isinstance(allow, list):
            return None
        # TTL expiry: ttl_hours > 0 → check created_at
        ttl = float(obj.get("ttl_hours") or 0)
        if ttl > 0:
            created = float(obj.get("created_at") or 0)
            if created and (created + ttl * 3600.0) < time.time():
                return None  # expired — treat as absent
        return obj
    except Exception:
        return None  # fail-open on any error


def write_sidecar(
    path: Path, key: str, key_type: str, allow: list[str], ttl_hours: float = 24.0
) -> bool:
    """Atomically write a sidecar. Returns True on success."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        obj = {
            "key": key,
            "key_type": key_type,
            "allow": allow,
            "created_at": time.time(),
            "ttl_hours": ttl_hours,
        }
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Glob matching — supports ** for zero-or-more path components
# ---------------------------------------------------------------------------


def _norm(p: str) -> str:
    """Normalize path separators to forward slashes."""
    return str(p or "").replace("\\", "/")


def _is_abs_pattern(pat: str) -> bool:
    """True for absolute patterns (Unix /foo or Windows C:/foo)."""
    return pat.startswith("/") or (len(pat) >= 2 and pat[1] == ":")


def _path_tails(norm_path: str) -> list[str]:
    """All suffix components of a normalized path for relative-pattern matching.

    For 'C:/project/src/foo.py' → [
      'C:/project/src/foo.py',
      'project/src/foo.py',
      'src/foo.py',
      'foo.py'
    ]
    For '/home/user/src/foo.py' → [
      '/home/user/src/foo.py',
      'home/user/src/foo.py',
      'user/src/foo.py',
      'src/foo.py',
      'foo.py'
    ]
    """
    result: list[str] = []
    if norm_path.startswith("/"):
        result.append(norm_path)
    parts = norm_path.lstrip("/").split("/")
    for i in range(len(parts)):
        tail = "/".join(parts[i:])
        if tail and tail not in result:
            result.append(tail)
    return result


def _glob_to_regex(pattern: str) -> str:
    """Convert a glob pattern to a regex string.

    Rules:
      **  followed by /  → zero or more path-component+separator groups
      **  at end / alone → anything (including nested paths)
      *                  → any characters within one path component (no /)
      ?                  → any single character (no /)
      Other              → re.escaped literal
    """
    result: list[str] = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern[i : i + 2] == "**":
            i += 2
            if i < len(pattern) and pattern[i] == "/":
                # Mid-path **: zero or more <component>/ groups
                result.append("(?:[^/]+/)*")
                i += 1  # consume the /
            else:
                # Trailing ** (or ** alone): match anything
                result.append(".*")
        elif ch == "*":
            result.append("[^/]*")
            i += 1
        elif ch == "?":
            result.append("[^/]")
            i += 1
        else:
            result.append(re.escape(ch))
            i += 1
    return "".join(result)


def matches_any(file_path: str, patterns: list[str]) -> bool:
    """Return True if file_path matches any glob pattern in the list.

    Absolute patterns are matched against the full normalized path only.
    Relative patterns are tried against every path tail so that a pattern
    like 'src/**/*.py' matches '/project/src/foo/bar.py' via the tail
    'src/foo/bar.py'.

    Windows note (H1 fix): on Windows (os.name == 'nt') both the path and
    each pattern are case-folded before comparison so that drive-letter /
    directory case differences — common between Claude Code's reported
    file_path and the sidecar allow-list — do not cause false blocks.
    _cwd_slug already lowercases for the same reason; this keeps matches_any
    consistent with that behaviour.
    """
    norm = _norm(file_path)
    if os.name == "nt":
        norm = norm.lower()
    tails = _path_tails(norm)

    for pattern in patterns:
        pat = _norm(pattern)
        if os.name == "nt":
            pat = pat.lower()
        if not pat:
            continue
        try:
            rx = re.compile(_glob_to_regex(pat) + r"\Z")
        except re.error:
            continue  # malformed pattern → skip (fail-open)

        is_abs = _is_abs_pattern(pat)
        if is_abs:
            if rx.fullmatch(norm):
                return True
        else:
            for tail in tails:
                if rx.fullmatch(tail):
                    return True

    return False


# ---------------------------------------------------------------------------
# Hook payload helpers
# ---------------------------------------------------------------------------


def read_stdin() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except Exception:
        return {}


def extract_session_id(data: dict) -> str:
    return (
        str((data or {}).get("session_id") or "default")
        .replace("/", "_")
        .replace("\\", "_")
    )
