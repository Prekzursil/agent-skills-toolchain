"""Build an isolated git history fixture in a temp directory.

Does not run git add/commit on the worktree. Commits use -c user.* so
global git config is never written.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from mechanism import DELETED_SYMBOL

HERE = Path(__file__).resolve().parent
ESTATE = HERE / "fixtures" / "estate"
DELETED_REL = "tools/retired/once-only-scanner.mjs"

_DELETED_SRC = f'''// Exists only in git history of the fixture repo.
export function {DELETED_SYMBOL}(payload) {{
  return String(payload);
}}
'''


def _git(cwd: Path, args: list[str]) -> None:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_AUTHOR_NAME"] = "bld-0033-fixture"
    env["GIT_AUTHOR_EMAIL"] = "bld-0033@invalid"
    env["GIT_COMMITTER_NAME"] = "bld-0033-fixture"
    env["GIT_COMMITTER_EMAIL"] = "bld-0033@invalid"
    p = subprocess.run(
        [
            "git",
            "-c",
            "user.name=bld-0033-fixture",
            "-c",
            "user.email=bld-0033@invalid",
            *args,
        ],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    if p.returncode != 0:
        raise RuntimeError(f"git {args} failed: {(p.stdout or '') + (p.stderr or '')}")


def build_history_repo(dest: Path | None = None) -> Path:
    """Copy the fixture estate into dest, commit, add then delete the symbol file."""
    root = Path(dest) if dest is not None else Path(tempfile.mkdtemp(prefix="bld0033-git-"))
    if root.exists():
        for child in root.iterdir():
            if child.name == ".git":
                shutil.rmtree(child)
            elif child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    else:
        root.mkdir(parents=True)
    tools_src = ESTATE / "tools"
    tools_dst = root / "tools"
    shutil.copytree(tools_src, tools_dst)
    _git(root, ["init", "-q"])
    _git(root, ["add", "tools"])
    _git(root, ["commit", "-q", "-m", "estate salvage + rebuilds"])
    retired = root / DELETED_REL
    retired.parent.mkdir(parents=True, exist_ok=True)
    retired.write_text(_DELETED_SRC, encoding="utf-8")
    _git(root, ["add", DELETED_REL])
    _git(root, ["commit", "-q", "-m", "add deleted-only symbol"])
    retired.unlink()
    _git(root, ["add", "-u", DELETED_REL])
    _git(root, ["commit", "-q", "-m", "delete once-only scanner"])
    return root
