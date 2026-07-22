"""Throwaway-git-repo helpers for the D-001 guard suite.

Uniquely named (not ``conftest``/``fixtures``) so that running this suite in the
same pytest session as ``tools/d001-dual-write/tests`` cannot resolve the wrong
module off ``sys.path``.

Every fixture is built from scratch in pytest's ``tmp_path`` and pins
``core.autocrlf=false``: on Windows the system-scope default is ``true``, which
rewrites LF to CRLF on checkout and silently changes blob identity under a test
that asserts on it.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

BASE_SKILL = "# existing-skill\n\nbase content\n"

REGULAR = "100644"
SYMLINK = "120000"
GITLINK = "160000"


class Repo:
    """A throwaway git repository with a helper API (no shell, no pipes)."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def git(self, *args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(self.root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            raise AssertionError(
                f"git {' '.join(args)} -> {proc.returncode}\n{proc.stderr}"
            )
        return proc.stdout

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    def write_bytes(self, rel: str, data: bytes) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def remove(self, rel: str) -> None:
        self.git("rm", "-q", "--", rel)

    def add(self, *rels: str) -> None:
        self.git("add", "--", *rels)

    def commit(self, message: str) -> str:
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD").strip()

    def hash_blob(self, data: bytes) -> str:
        """Write a blob straight into the object database."""
        proc = subprocess.run(
            ["git", "-C", str(self.root), "hash-object", "-w", "--stdin"],
            input=data,
            capture_output=True,
        )
        if proc.returncode != 0:
            raise AssertionError(proc.stderr.decode(errors="replace"))
        return proc.stdout.decode().strip()

    def plumb_branch(
        self, entries: dict[str, tuple[str, str]], branch: str, base: str = "main"
    ) -> str:
        """Build ``branch`` = ``base`` + ``entries`` in a TEMPORARY index.

        ``entries`` maps a path to ``(mode, oid)``.  Everything happens in the
        object database, so a path that a Windows working tree cannot hold -- a
        name containing a NEWLINE, or a symlink -- can still be committed and
        diffed here.  ``core.protectNTFS=false`` lifts a Windows-LOCAL authoring
        restriction only; the gate itself runs on ubuntu-latest, where such a
        name is ordinary and needs no flag at all.
        """
        fd, index = tempfile.mkstemp(prefix="dual-write-index-")
        os.close(fd)
        os.unlink(index)
        env = {**os.environ, "GIT_INDEX_FILE": index}
        try:
            for args in (
                ["read-tree", base],
                *[
                    [
                        "-c",
                        "core.protectNTFS=false",
                        "update-index",
                        "--add",
                        "--cacheinfo",
                        f"{mode},{oid},{path}",
                    ]
                    for path, (mode, oid) in entries.items()
                ],
            ):
                proc = subprocess.run(
                    ["git", "-C", str(self.root), *args],
                    capture_output=True,
                    text=True,
                    env=env,
                )
                if proc.returncode != 0:
                    raise AssertionError(f"git {args} -> {proc.stderr}")
            tree = subprocess.run(
                ["git", "-C", str(self.root), "write-tree"],
                capture_output=True,
                text=True,
                env=env,
            ).stdout.strip()
        finally:
            if os.path.exists(index):
                os.unlink(index)
        parent = self.git("rev-parse", f"{base}^{{commit}}").strip()
        commit = self.git("commit-tree", tree, "-p", parent, "-m", branch).strip()
        self.git("update-ref", f"refs/heads/{branch}", commit)
        return commit


def init_repo(root: Path) -> Repo:
    root.mkdir(parents=True, exist_ok=True)
    r = Repo(root)
    r.git("init", "-q", "-b", "main")
    r.git("config", "user.name", "fixture")
    r.git("config", "user.email", "fixture@example.invalid")
    r.git("config", "core.autocrlf", "false")
    r.git("config", "commit.gpgsign", "false")
    return r


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    """Repo on branch ``main`` with one skill in parity across both trees."""
    r = init_repo(tmp_path / "fixture-repo")
    r.write("skills/existing-skill/SKILL.md", BASE_SKILL)
    r.write(".agents/skills/existing-skill/SKILL.md", BASE_SKILL)
    r.write("skills/SKILLS-MANIFEST.md", "# manifest\n")
    r.add("skills", ".agents")
    r.commit("base")
    r.git("checkout", "-q", "-b", "feature")
    return r
