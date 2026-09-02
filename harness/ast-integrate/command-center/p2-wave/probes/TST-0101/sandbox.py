"""Isolated git sandbox. Never touches the shared worktree index."""
from __future__ import annotations

import os
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

SHARED_ROOT = Path(__file__).resolve().parents[4]


class SandboxError(RuntimeError):
    pass


def _assert_isolated(root: Path) -> None:
    sandbox = root.resolve()
    shared = SHARED_ROOT.resolve()
    if sandbox == shared:
        raise SandboxError("refusing to use the shared worktree as a git sandbox")
    try:
        sandbox.relative_to(shared)
    except ValueError:
        return
    raise SandboxError(f"sandbox {sandbox} is inside shared worktree {shared}")


def isolated_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["GIT_AUTHOR_NAME"] = "TST-0101"
    env["GIT_AUTHOR_EMAIL"] = "tst-0101@example.test"
    env["GIT_COMMITTER_NAME"] = "TST-0101"
    env["GIT_COMMITTER_EMAIL"] = "tst-0101@example.test"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    env.pop("GIT_INDEX_FILE", None)
    return env


class GitSandbox:
    def __init__(self, root: Path) -> None:
        _assert_isolated(root)
        self.root = root
        self.env = isolated_env(root)

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        _assert_isolated(self.root)
        cmd = [
            "git",
            "-c",
            "init.defaultBranch=main",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.autocrlf=false",
            "-C",
            str(self.root),
            *args,
        ]
        proc = subprocess.run(
            cmd,
            cwd=str(self.root),
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )
        if check and proc.returncode != 0:
            raise SandboxError(
                f"git {' '.join(args)} rc={proc.returncode} "
                f"stderr={(proc.stderr or '').strip()[-800:]}"
            )
        return proc

    def init(self) -> None:
        self.git("init", "-b", "main")
        self.git("config", "user.name", "TST-0101")
        self.git("config", "user.email", "tst-0101@example.test")

    def write(self, rel: str, content: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def rm(self, rel: str) -> None:
        path = self.root / rel
        if path.is_file():
            path.unlink()

    def commit_all(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-m", message)
        return self.git("rev-parse", "HEAD").stdout.strip()

    def checkout(self, ref: str, create: bool = False) -> None:
        if create:
            self.git("checkout", "-b", ref)
        else:
            self.git("checkout", ref)

    def sha(self, ref: str = "HEAD") -> str:
        return self.git("rev-parse", ref).stdout.strip()

    def tree(self, ref: str) -> str:
        return self.git("rev-parse", f"{ref}^{{tree}}").stdout.strip()


@contextmanager
def temporary_sandbox(prefix: str = "tst0101-"):
    with tempfile.TemporaryDirectory(prefix=prefix, dir="/tmp") as td:
        root = Path(td)
        _assert_isolated(root)
        box = GitSandbox(root)
        box.init()
        yield box
