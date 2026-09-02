"""Fixture git histories for CNF-0022 time-travel (created only under /tmp)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

ADD_BAD = "def add(a, b):\n    return a + b + 1\n"
ADD_GOOD = "def add(a, b):\n    return a + b\n"
ADD_GOOD_COMMENT = (
    "def add(a, b):\n"
    "    # labelled fix: overflow — comment only, arithmetic unchanged\n"
    "    return a + b\n"
)
MUL_BAD = "def mul(a, b):\n    return a * b + 1\n"
MUL_GOOD = "def mul(a, b):\n    return a * b\n"
TEST_ADD = """import sys
import buggy

got = buggy.add(2, 2)
if got != 4:
    print(f"RED: add(2,2)={got} want=4")
    sys.exit(1)
print("GREEN: add(2,2)==4")
sys.exit(0)
"""
TEST_MUL = """import sys
import mul

got = mul.mul(3, 3)
if got != 9:
    print(f"RED: mul(3,3)={got} want=9")
    sys.exit(1)
print("GREEN: mul(3,3)==9")
sys.exit(0)
"""

FIXTURES = (
    {
        "id": "FIX-ADD-OFFBYONE",
        "title": "off-by-one in add() with a test that sees the defect",
        "test_rel": "test_add.py",
        "expected_pattern": "RED-GREEN",
        "expected_classification": "confirmed-defect-at-parent",
        "parent_files": {"buggy.py": ADD_BAD, "test_add.py": TEST_ADD},
        "fix_files": {"buggy.py": ADD_GOOD, "test_add.py": TEST_ADD},
        "parent_message": "parent: add() returns a+b+1",
        "fix_message": "fix: add() returns a+b",
        "control_rel": None,
    },
    {
        "id": "FIX-COMMENT-ONLY",
        "title": "comment-only commit labelled as the add() fix",
        "test_rel": "test_add.py",
        "expected_pattern": "GREEN-GREEN",
        "expected_classification": "misattributed-fix",
        "parent_files": {"buggy.py": ADD_GOOD, "test_add.py": TEST_ADD},
        "fix_files": {"buggy.py": ADD_GOOD_COMMENT, "test_add.py": TEST_ADD},
        "parent_message": "parent: add() already correct",
        "fix_message": "fix: comment claiming overflow repair",
        "control_rel": None,
    },
    {
        "id": "FIX-MUL-WITH-ADD-TEST",
        "title": "mul() fix associated with the add() test",
        "test_rel": "test_add.py",
        "expected_pattern": "GREEN-GREEN",
        "expected_classification": "test-measures-something-else",
        "parent_files": {
            "buggy.py": ADD_GOOD,
            "mul.py": MUL_BAD,
            "test_add.py": TEST_ADD,
            "test_mul.py": TEST_MUL,
        },
        "fix_files": {
            "buggy.py": ADD_GOOD,
            "mul.py": MUL_GOOD,
            "test_add.py": TEST_ADD,
            "test_mul.py": TEST_MUL,
        },
        "parent_message": "parent: mul() off-by-one, add() already correct",
        "fix_message": "fix: mul() returns a*b",
        "control_rel": "test_mul.py",
        "control_expected_pattern": "RED-GREEN",
    },
)

DATES = (
    "2026-08-01T12:00:00 +0000",
    "2026-08-01T12:01:00 +0000",
)


def _git_env(home: Path, date: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "CNF-0022 fixture",
            "GIT_AUTHOR_EMAIL": "cnf-0022@fixture.local",
            "GIT_COMMITTER_NAME": "CNF-0022 fixture",
            "GIT_COMMITTER_EMAIL": "cnf-0022@fixture.local",
            "GIT_AUTHOR_DATE": date,
            "GIT_COMMITTER_DATE": date,
            "EMAIL": "cnf-0022@fixture.local",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return env


def assert_isolated(path: Path) -> Path:
    cwd = path.resolve()
    shared = REPO.resolve()
    if cwd == shared or shared in cwd.parents:
        raise RuntimeError(f"refusing git path inside shared worktree: {cwd}")
    return cwd


def git(args: list[str], cwd: Path, env: dict[str, str], check: bool = True) -> subprocess.CompletedProcess:
    cwd = assert_isolated(cwd)
    proc = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"git {args} rc={proc.returncode} cwd={cwd}\n"
            f"{(proc.stdout or '') + (proc.stderr or '')}"
        )
    return proc


def _write_tree(root: Path, files: dict[str, str]) -> None:
    for rel, body in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8", newline="\n")


def build_repo(spec: dict, dest: Path) -> dict:
    dest = assert_isolated(dest)
    dest.mkdir(parents=True, exist_ok=True)
    home = dest / ".home"
    home.mkdir(exist_ok=True)
    env0 = _git_env(home, DATES[0])
    git(["init", "--object-format=sha1", "-b", "main"], dest, env0)
    _write_tree(dest, spec["parent_files"])
    git(["add", "-A"], dest, env0)
    git(["commit", "-m", spec["parent_message"]], dest, env0)
    parent_sha = git(["rev-parse", "HEAD"], dest, env0).stdout.strip()
    env1 = _git_env(home, DATES[1])
    _write_tree(dest, spec["fix_files"])
    git(["add", "-A"], dest, env1)
    git(["commit", "-m", spec["fix_message"]], dest, env1)
    fix_sha = git(["rev-parse", "HEAD"], dest, env1).stdout.strip()
    return {
        **spec,
        "repo": dest,
        "parent_sha": parent_sha,
        "fix_sha": fix_sha,
        "home": home,
        "env": env1,
    }


def build_all(base: Path) -> list[dict]:
    base = assert_isolated(base)
    built = []
    for spec in FIXTURES:
        built.append(build_repo(spec, base / spec["id"]))
    return built
