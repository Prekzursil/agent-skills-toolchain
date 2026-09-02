"""Isolated git fixture for CNF-0163 controls.

Created in a tempfile. Does not touch the delivery worktree's git state
(there is none). core.autocrlf is forced off so blob bytes are exactly
what we write.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

EVIDENCE_A = (
    "ALPHA-CONSTRUCT lives here\n"
    "BETA-CONSTRUCT lives here\n"
    "GAMMA-CONSTRUCT lives here\n"
)
EVIDENCE_B = (
    "INSERTED-HEADER\n"
    "ALPHA-CONSTRUCT lives here\n"
    "BETA-CONSTRUCT lives here\n"
    "GAMMA-CONSTRUCT lives here\n"
)
WORKTREE_ONLY_LINE = "WORKTREE-ONLY-CONSTRUCT lives here\n"
EVIDENCE_REL = "evidence.txt"
EOL_REL = "eol.txt"


@dataclass
class Fixture:
    repo: Path
    rev_a: str
    rev_b: str
    evidence_rel: str
    eol_rel: str


def _git(repo: Path, *args: str, env: dict) -> subprocess.CompletedProcess:
    cmd = [
        "git",
        "-C",
        str(repo),
        "-c",
        "core.autocrlf=false",
        "-c",
        "user.name=CNF-0163",
        "-c",
        "user.email=cnf-0163@local.test",
        *args,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"git {args} failed: {r.stderr or r.stdout}")
    return r


@contextmanager
def make_fixture() -> Iterator[Fixture]:
    tmp = Path(tempfile.mkdtemp(prefix="cnf0163-fix-"))
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "CNF-0163",
            "GIT_AUTHOR_EMAIL": "cnf-0163@local.test",
            "GIT_COMMITTER_NAME": "CNF-0163",
            "GIT_COMMITTER_EMAIL": "cnf-0163@local.test",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    try:
        _git(tmp, "init", "-q", env=env)
        (tmp / EVIDENCE_REL).write_bytes(EVIDENCE_A.encode("utf-8"))
        (tmp / EOL_REL).write_bytes(EVIDENCE_A.encode("utf-8"))
        _git(tmp, "add", "-A", env=env)
        _git(tmp, "commit", "-q", "-m", "rev-a present", env=env)
        rev_a = _git(tmp, "rev-parse", "HEAD", env=env).stdout.strip()

        (tmp / EVIDENCE_REL).write_bytes(EVIDENCE_B.encode("utf-8"))
        _git(tmp, "add", EVIDENCE_REL, env=env)
        _git(tmp, "commit", "-q", "-m", "rev-b drift", env=env)
        rev_b = _git(tmp, "rev-parse", "HEAD", env=env).stdout.strip()

        (tmp / EVIDENCE_REL).write_bytes(
            (EVIDENCE_B + WORKTREE_ONLY_LINE).encode("utf-8")
        )
        crlf = EVIDENCE_A.replace("\n", "\r\n").encode("utf-8")
        (tmp / EOL_REL).write_bytes(crlf)

        yield Fixture(
            repo=tmp,
            rev_a=rev_a,
            rev_b=rev_b,
            evidence_rel=EVIDENCE_REL,
            eol_rel=EOL_REL,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def worktree_cr_construct(fix: Fixture, line: int = 1) -> str:
    """Exact worktree line including a trailing CR — the EOL trap."""
    raw = (fix.repo / fix.eol_rel).read_bytes()
    logical = raw.split(b"\n")
    if line < 1 or line > len(logical):
        raise AssertionError("eol worktree line oob")
    piece = logical[line - 1]
    if piece.endswith(b"\r"):
        return piece.decode("utf-8")
    raise AssertionError("EOL fixture worktree line has no CR")
