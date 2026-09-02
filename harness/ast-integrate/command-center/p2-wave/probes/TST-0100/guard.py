"""Worktree origin-URL write guard for TST-0100 / FC-11321.

Before any file write, resolve `origin` with a git command and refuse when
it does not match the pinned program repository. The worktree *path string*
is never a substitute for origin: a directory named like the pin with a
foreign remote must be refused, and an unrelated path with the pinned
remote must be permitted.

A missing origin is refused (never default-allow). That is the
missing-origin-defaults-allow failure class from IMP-0432.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIN_FILE = HERE / "pinned-origin.txt"
GIT_TIMEOUT_S = 20


class WrongRepoError(RuntimeError):
    """Raised when a write is attempted outside the pinned origin."""


@dataclass
class OriginResolution:
    worktree: Path
    command: list[str]
    git_exit: int
    origin: str | None
    stderr: str
    stdout: str


@dataclass
class GuardedWrite:
    allowed: bool
    reason: str
    origin: str | None
    pinned: str
    command: list[str]
    git_exit: int
    worktree: Path
    dest: Path
    wrote: bool
    bytes_written: int = 0
    stderr: str = ""
    extras: dict = field(default_factory=dict)


def load_pin(path: Path | None = None) -> str:
    pin_path = path or PIN_FILE
    text = pin_path.read_text(encoding="utf-8")
    line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    if not line:
        raise WrongRepoError("pinned origin file is empty")
    return line


def normalize_origin(url: str) -> str:
    """Compare remotes, not path strings or URL spelling accidents."""
    u = (url or "").strip()
    if not u:
        return ""
    if u.startswith("git@"):
        host, _, path = u[4:].partition(":")
        u = f"https://{host}/{path}"
    elif u.startswith("ssh://"):
        rest = u[6:]
        if "@" in rest:
            rest = rest.split("@", 1)[1]
        u = "https://" + rest
    while u.endswith("/"):
        u = u[:-1]
    if u.lower().endswith(".git"):
        u = u[:-4]
    if "://" in u:
        scheme, rest = u.split("://", 1)
        if "/" in rest:
            host, path = rest.split("/", 1)
            u = f"{scheme.lower()}://{host.lower()}/{path}"
        else:
            u = f"{scheme.lower()}://{rest.lower()}"
    return u


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    return env


def resolve_origin(worktree: Path) -> OriginResolution:
    """Resolve origin by git command, never by inspecting the path string.

    Command: git -C <worktree> remote get-url origin
    """
    wt = Path(worktree).resolve()
    cmd = ["git", "-C", str(wt), "remote", "get-url", "origin"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            env=_git_env(),
        )
    except FileNotFoundError:
        return OriginResolution(
            worktree=wt,
            command=cmd,
            git_exit=127,
            origin=None,
            stderr="git executable not found",
            stdout="",
        )
    except subprocess.TimeoutExpired:
        return OriginResolution(
            worktree=wt,
            command=cmd,
            git_exit=124,
            origin=None,
            stderr="git remote get-url timed out",
            stdout="",
        )
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    origin = stdout if proc.returncode == 0 and stdout else None
    return OriginResolution(
        worktree=wt,
        command=cmd,
        git_exit=proc.returncode,
        origin=origin,
        stderr=stderr,
        stdout=stdout,
    )


def guarded_write(
    worktree: Path,
    rel: str,
    data: bytes,
    pinned: str | None = None,
) -> GuardedWrite:
    """Write `rel` under worktree only after origin matches the pin.

    The check runs before mkdir or write. A refusal leaves no new file.
    """
    wt = Path(worktree)
    dest = wt / rel
    pin = pinned if pinned is not None else load_pin()
    if not wt.is_dir():
        return GuardedWrite(
            allowed=False,
            reason="not-a-directory",
            origin=None,
            pinned=pin,
            command=[],
            git_exit=2,
            worktree=wt,
            dest=dest,
            wrote=False,
        )
    resolved = resolve_origin(wt)
    if resolved.origin is None:
        return GuardedWrite(
            allowed=False,
            reason="missing-origin",
            origin=None,
            pinned=pin,
            command=resolved.command,
            git_exit=resolved.git_exit,
            worktree=resolved.worktree,
            dest=dest,
            wrote=False,
            stderr=resolved.stderr,
            extras={"stdout": resolved.stdout},
        )
    if normalize_origin(resolved.origin) != normalize_origin(pin):
        return GuardedWrite(
            allowed=False,
            reason="origin-mismatch",
            origin=resolved.origin,
            pinned=pin,
            command=resolved.command,
            git_exit=resolved.git_exit,
            worktree=resolved.worktree,
            dest=dest,
            wrote=False,
            stderr=resolved.stderr,
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return GuardedWrite(
        allowed=True,
        reason="origin-matches-pin",
        origin=resolved.origin,
        pinned=pin,
        command=resolved.command,
        git_exit=resolved.git_exit,
        worktree=resolved.worktree,
        dest=dest,
        wrote=True,
        bytes_written=len(data),
        stderr=resolved.stderr,
    )
