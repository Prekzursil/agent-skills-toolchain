"""git status --porcelain=v2 -uall plus per-path size and mtime.

The live worktree /opt/p2/ast-integrate has no .git (verified). Porcelain still
runs against a throwaway fixture repo that holds the planted-mutant controls so
the named probe actually executes git, not a paraphrase of git.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONTROL_REAL = HERE / "control" / "tmp" / "scratch_cache" / "real_module.py"
CONTROL_JUNK = HERE / "control" / "src" / "core" / "session_state.py"


def parse_porcelain_v2(raw: str) -> list[dict[str, str]]:
    """Parse git status --porcelain=v2 -uall. Paths only; no body copy."""
    out: list[dict[str, str]] = []
    for line in raw.splitlines():
        if not line:
            continue
        tag = line[0]
        if tag in "12":
            fields = line.split(" ", 8)
            path = fields[8] if len(fields) > 8 else ""
            if tag == "2" and "\t" in path:
                path = path.split("\t", 1)[0]
            out.append({"path": path, "xy": fields[1] if len(fields) > 1 else "", "kind": "tracked-change"})
        elif tag == "?":
            out.append({"path": line[2:], "xy": "??", "kind": "untracked"})
        elif tag == "u":
            fields = line.split(" ", 10)
            out.append(
                {
                    "path": fields[10] if len(fields) > 10 else "",
                    "xy": fields[1] if len(fields) > 1 else "",
                    "kind": "unmerged",
                }
            )
        elif tag == "!":
            out.append({"path": line[2:], "xy": "!!", "kind": "ignored"})
    return out


def run_git_porcelain(cwd: Path, timeout: int = 120) -> tuple[int, str]:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain=v2", "-uall"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT: git status --porcelain=v2 -uall"
    except OSError as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    text = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, text


def attach_size_mtime(repo: Path, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for e in entries:
        fp = repo / e["path"]
        if fp.is_file():
            st = fp.stat()
            e["bytes"] = st.st_size
            e["mtime"] = st.st_mtime
            e["on_disk"] = True
        else:
            e["bytes"] = 0
            e["mtime"] = None
            e["on_disk"] = False
    return entries


def live_git_status(repo: Path = REPO) -> dict[str, Any]:
    git_dir = repo / ".git"
    rc, raw = run_git_porcelain(repo)
    return {
        "repo": str(repo),
        "git_dir_present": git_dir.exists(),
        "exit_code": rc,
        "raw_head": raw[:4000],
        "is_git_worktree": rc == 0,
        "error": None if rc == 0 else raw.strip()[:500],
    }


def build_fixture_repo() -> tuple[Path, list[dict[str, Any]], str, int]:
    """Create a throwaway git repo with both planted mutants as untracked files.

    Does not git add/commit. Caller must delete the directory.
    """
    tmp = Path(tempfile.mkdtemp(prefix="aud0006-porcelain-"))
    init = subprocess.run(
        ["git", "init", "-q"],
        cwd=str(tmp),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if init.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(f"git init failed: {init.stderr or init.stdout}")
    real_dst = tmp / "tmp" / "scratch_cache" / "real_module.py"
    junk_dst = tmp / "src" / "core" / "session_state.py"
    real_dst.parent.mkdir(parents=True, exist_ok=True)
    junk_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CONTROL_REAL, real_dst)
    shutil.copy2(CONTROL_JUNK, junk_dst)
    rc, raw = run_git_porcelain(tmp)
    entries = attach_size_mtime(tmp, parse_porcelain_v2(raw))
    return tmp, entries, raw, rc
