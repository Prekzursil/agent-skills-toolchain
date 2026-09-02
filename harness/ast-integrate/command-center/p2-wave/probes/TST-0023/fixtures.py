"""Isolated git fixtures for TST-0023. Never mutates the delivery worktree."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from baseline.capture import git, git_env, git_text  # noqa: E402

PAYLOAD: dict[str, bytes] = {
    "README.md": b"# TST-0023 fixture\n",
    "hooks/pre-commit": b"#!/bin/sh\nexit 0\n",
    "skills/demo/SKILL.md": b"# demo skill\n",
    "plugins/settings.json": b'{"theme":"fixture"}\n',
    "marketplaces/index.json": b'{"packages":[]}\n',
    ".mcp.json": b'{"mcpServers":{}}\n',
    "mcp/server.json": b'{"name":"fixture-mcp"}\n',
}


def init_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=str(root),
        check=True,
        capture_output=True,
        env=git_env(),
    )
    git(root, "config", "core.autocrlf", "false")
    git(root, "config", "advice.detachedHead", "false")
    git(root, "config", "user.name", "TST-0023")
    git(root, "config", "user.email", "tst-0023@local")
    return root


def write_files(root: Path, files: dict[str, bytes]) -> None:
    for rel, data in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def commit_files(root: Path, files: dict[str, bytes], message: str) -> str:
    write_files(root, files)
    for rel in files:
        git(root, "add", "--", rel)
    git(root, "commit", "-m", message)
    return git_text(root, "rev-parse", "HEAD").strip()


def build_clean_fixture(root: Path) -> str:
    init_repo(root)
    return commit_files(root, PAYLOAD, "TST-0023 pinned payload")
