#!/usr/bin/env python3
"""TST-0100 write-guard: origin resolved by git command, not path string.

check_write(worktree, rel_path) runs `git -C <worktree> remote get-url
origin`, normalizes the URL, and only permits the write when it equals
the pinned origin. Missing origin refuses (never default-allow). The
verdict is the git COMMAND's answer: a path that looks like the pin but
whose origin is foreign is refused; an unrelated path whose origin is
the pin is permitted."""
from __future__ import annotations

import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def pinned_origin() -> str:
    return (HERE / "pinned-origin.txt").read_text(encoding="utf-8").strip()


def normalize(url: str) -> str:
    u = (url or "").strip().casefold()
    if u.endswith(".git"):
        u = u[:-4]
    if u.endswith("/"):
        u = u[:-1]
    return u


def resolve_origin(worktree: str | Path) -> tuple[str | None, str]:
    p = subprocess.run(["git", "-C", str(worktree), "remote", "get-url", "origin"],
                       capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        return None, (p.stderr or "").strip().splitlines()[-1] if (p.stderr or "").strip() else "no origin"
    return p.stdout.strip(), "origin-resolved"


def check_write(worktree: str | Path, rel_path: str = "scratch.txt") -> dict:
    origin, note = resolve_origin(worktree)
    pin = normalize(pinned_origin())
    if origin is None:
        return {"allowed": False, "reason": "missing-origin", "origin": None, "note": note}
    if normalize(origin) == pin:
        target = Path(worktree) / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("guard-permitted-write\n", encoding="utf-8")
        return {"allowed": True, "reason": "origin-matches-pin", "origin": origin, "note": note}
    return {"allowed": False, "reason": "origin-mismatch", "origin": origin, "note": note}
