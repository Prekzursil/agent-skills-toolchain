"""Worktree-target repository assertion before any file write (IMP-0432).

Failure class (spec :11321): a worktree that points at the wrong repository.
Before mkdir or write, resolve `origin` with a git command and PERMIT only when
the normalized URL matches the pinned program repo. A directory whose path
contains the pin token is not an origin. A missing origin is REFUSE, never
default-allow.

Public surface used by command-center/p2-wave/probes/IMP-0432/:

    load_pin, git_clean_env, resolve_origin_url, guarded_write, table_row
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping

GIT_TIMEOUT_S = 30
REASON_MATCH = "MATCH"
REASON_WRONG_REPO = "WRONG_REPO"
REASON_MISSING_ORIGIN = "MISSING_ORIGIN"
REASON_PIN_INVALID = "PIN_INVALID"
DECISION_PERMIT = "PERMIT"
DECISION_REFUSE = "REFUSE"
FAILURE_WRONG_REPO = "wrong-repo-write"
FAILURE_MISSING_ORIGIN = "missing-origin-defaults-allow"
RESOLVED_BY_GIT = "git-command"

# Inherited git identity vars would make `git -C <other>` read the caller's
# repo. Strip them so origin is always the target worktree's remote.
_GIT_IDENTITY_UNSET = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_PREFIX",
    "GIT_NAMESPACE",
)


def git_clean_env() -> dict[str, str]:
    """Env for git subprocesses: no prompts, no caller GIT_DIR, no global config."""
    env = os.environ.copy()
    for key in _GIT_IDENTITY_UNSET:
        env.pop(key, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


def load_pin(path: Path | str) -> dict[str, Any]:
    """Load the pinned-origin document. Caller supplies the path; no default-allow."""
    pin_path = Path(path)
    raw = json.loads(pin_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"pinned origin is not a JSON object: {pin_path}")
    urls = raw.get("pinned_origin_urls")
    if not isinstance(urls, list) or not urls:
        raise ValueError(f"pinned_origin_urls missing or empty: {pin_path}")
    return raw


def normalize_origin(url: str | None) -> str | None:
    """Compare remotes, not path strings or URL spelling accidents.

    https://host/path.git and git@host:path.git normalize to the same value.
    Empty input returns None so a missing origin stays distinct from a match.
    """
    if url is None:
        return None
    u = str(url).strip()
    if not u:
        return None
    if u.startswith("git@") and "://" not in u:
        host, _, path = u[4:].partition(":")
        u = f"https://{host}/{path.lstrip('/')}"
    elif u.startswith("ssh://"):
        rest = u[6:]
        authority, slash, tail = rest.partition("/")
        if "@" in authority:
            authority = authority.rsplit("@", 1)[-1]
        u = "https://" + authority + (slash + tail if slash else "")
    elif u.startswith("git://"):
        u = "https://" + u[6:]
    while u.endswith("/"):
        u = u[:-1]
    if u.lower().endswith(".git"):
        u = u[:-4]
    if "://" not in u:
        return u or None
    scheme, rest = u.split("://", 1)
    if "/" in rest:
        host, path = rest.split("/", 1)
        if "@" in host:
            host = host.rsplit("@", 1)[-1]
        return f"{scheme.lower()}://{host.lower()}/{path}"
    host = rest
    if "@" in host:
        host = host.rsplit("@", 1)[-1]
    return f"{scheme.lower()}://{host.lower()}"


def _existing_ancestor(path: Path) -> Path:
    cursor = path
    while not cursor.exists() and cursor.parent != cursor:
        cursor = cursor.parent
    return cursor


def discover_worktree(target: Path) -> Path:
    """Walk parents for a .git marker. This is git-dir discovery, not origin."""
    start = target if target.exists() and target.is_dir() else target.parent
    start = _existing_ancestor(start)
    probe = start
    while True:
        marker = probe / ".git"
        if marker.is_dir() or marker.is_file():
            return probe
        if probe.parent == probe:
            return start
        probe = probe.parent


def resolve_origin_url(worktree: Path | str) -> dict[str, Any]:
    """Resolve origin by `git remote get-url`. Never by inspecting the path string."""
    wt = Path(worktree)
    cmd = ["git", "-C", str(wt), "remote", "get-url", "origin"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=git_clean_env(),
            timeout=GIT_TIMEOUT_S,
            check=False,
        )
    except FileNotFoundError:
        return {
            "ok": False,
            "url": None,
            "command": cmd,
            "git_exit": 127,
            "stdout": "",
            "stderr": "git executable not found",
            "path_string_used_as_origin": False,
            "resolved_by": RESOLVED_BY_GIT,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "url": None,
            "command": cmd,
            "git_exit": 124,
            "stdout": "",
            "stderr": "git remote get-url timed out",
            "path_string_used_as_origin": False,
            "resolved_by": RESOLVED_BY_GIT,
        }
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    ok = proc.returncode == 0 and bool(stdout)
    return {
        "ok": ok,
        "url": stdout if ok else None,
        "command": cmd,
        "git_exit": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "path_string_used_as_origin": False,
        "resolved_by": RESOLVED_BY_GIT,
    }


def _pin_url_set(pin_doc: Mapping[str, Any]) -> set[str]:
    urls = pin_doc.get("pinned_origin_urls") or []
    out: set[str] = set()
    if isinstance(urls, list):
        for item in urls:
            norm = normalize_origin(str(item) if item is not None else None)
            if norm:
                out.add(norm)
    return out


def assert_origin(target: Path | str, pin_doc: Mapping[str, Any]) -> dict[str, Any]:
    """Verdict only. Does not mkdir, write, or mutate the target."""
    dest = Path(target)
    worktree = discover_worktree(dest)
    pins = _pin_url_set(pin_doc)
    resolved = resolve_origin_url(worktree)
    cmd = list(resolved.get("command") or [])
    origin = resolved.get("url")
    normalized = normalize_origin(origin if isinstance(origin, str) else None)

    def verdict(
        decision: str,
        reason: str,
        *,
        failure_class: str | None,
    ) -> dict[str, Any]:
        return {
            "decision": decision,
            "reason": reason,
            "resolved_origin_url": origin if isinstance(origin, str) else None,
            "normalized_origin": normalized,
            "git_command": cmd,
            "path_string_used_as_origin": False,
            "resolved_by": RESOLVED_BY_GIT,
            "worktree": str(worktree),
            "path": str(worktree),
            "target": str(dest),
            "failure_class": failure_class,
            "git_exit": resolved.get("git_exit"),
        }

    if not pins:
        return verdict(DECISION_REFUSE, REASON_PIN_INVALID, failure_class=FAILURE_WRONG_REPO)
    if not resolved.get("ok") or origin is None:
        # Missing origin is refused even if a caller flipped the pin flag.
        # The pin documents the policy; the guard enforces it.
        return verdict(
            DECISION_REFUSE,
            REASON_MISSING_ORIGIN,
            failure_class=FAILURE_MISSING_ORIGIN,
        )
    if normalized is None or normalized not in pins:
        return verdict(DECISION_REFUSE, REASON_WRONG_REPO, failure_class=FAILURE_WRONG_REPO)
    return verdict(DECISION_PERMIT, REASON_MATCH, failure_class=None)


def guarded_write(
    target: Path | str,
    data: bytes,
    pin_doc: Mapping[str, Any],
) -> dict[str, Any]:
    """Write `target` only after origin matches the pin.

    The origin check runs before mkdir or write. A REFUSE leaves the tree
    untouched: no new file, no truncated pre-seeded marker.
    """
    dest = Path(target)
    if isinstance(data, str):
        payload = data.encode("utf-8")
    else:
        payload = bytes(data)
    verdict = assert_origin(dest, pin_doc)
    write_performed = False
    if verdict["decision"] == DECISION_PERMIT:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        write_performed = True
    return {
        "verdict": verdict,
        "write_performed": write_performed,
        "target": str(dest),
        "worktree": verdict.get("worktree"),
        "bytes_written": len(payload) if write_performed else 0,
    }


def table_row(result: Mapping[str, Any]) -> dict[str, Any]:
    """Evidence row: path, resolved origin URL, match verdict, write_performed."""
    verdict = result.get("verdict") or {}
    if not isinstance(verdict, Mapping):
        verdict = {}
    reason = verdict.get("reason")
    decision = verdict.get("decision")
    failure = verdict.get("failure_class")
    if failure is None:
        if reason == REASON_WRONG_REPO:
            failure = FAILURE_WRONG_REPO
        elif reason == REASON_MISSING_ORIGIN:
            failure = FAILURE_MISSING_ORIGIN
    return {
        "failure_class": failure,
        "git_command": list(verdict.get("git_command") or []),
        "match_verdict": decision,
        "normalized_origin": verdict.get("normalized_origin"),
        "path": verdict.get("path") or verdict.get("worktree"),
        "path_string_used_as_origin": bool(verdict.get("path_string_used_as_origin")),
        "reason": reason,
        "resolved_by": verdict.get("resolved_by") or RESOLVED_BY_GIT,
        "resolved_origin_url": verdict.get("resolved_origin_url"),
        "target": result.get("target") or verdict.get("target"),
        "write_performed": bool(result.get("write_performed")),
    }


__all__ = (
    "DECISION_PERMIT",
    "DECISION_REFUSE",
    "REASON_MATCH",
    "REASON_MISSING_ORIGIN",
    "REASON_WRONG_REPO",
    "assert_origin",
    "discover_worktree",
    "git_clean_env",
    "guarded_write",
    "load_pin",
    "normalize_origin",
    "resolve_origin_url",
    "table_row",
)
