#!/usr/bin/env python3
"""Live developer-tree vs fresh-clone comparison for CNF-0030.

Isolated fixture git repositories live only under tempfile. This module never
runs git add/commit/checkout against the product worktree.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TEST_SRC = HERE / "fixtures" / "test_payload.py"
PAYLOAD_TEXT = "CNF-0030-FIX-PAYLOAD\n"
MISSING_FILE = "required_payload.txt"
PINNED_DATE = "2026-08-24T18:00:00+0000"
GIT_IDENT = [
    "-c",
    "user.name=CNF-0030",
    "-c",
    "user.email=cnf-0030@fixture.local",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "init.defaultBranch=main",
    "-c",
    "safe.directory=*",
]


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_AUTHOR_NAME"] = "CNF-0030"
    env["GIT_AUTHOR_EMAIL"] = "cnf-0030@fixture.local"
    env["GIT_COMMITTER_NAME"] = "CNF-0030"
    env["GIT_COMMITTER_EMAIL"] = "cnf-0030@fixture.local"
    env["GIT_AUTHOR_DATE"] = PINNED_DATE
    env["GIT_COMMITTER_DATE"] = PINNED_DATE
    env["EMAIL"] = "cnf-0030@fixture.local"
    return env


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *GIT_IDENT, *args],
        cwd=str(cwd),
        env=git_env(),
        capture_output=True,
        text=True,
        check=False,
    )


def die_git(proc: subprocess.CompletedProcess[str], what: str) -> None:
    if proc.returncode != 0:
        tail = ((proc.stdout or "") + (proc.stderr or "")).strip()[-1500:]
        raise RuntimeError(f"{what} rc={proc.returncode} {tail}")


def test_command() -> str:
    return f"{sys.executable} -B test_payload.py"


def run_test(tree: Path) -> dict:
    cmd = test_command()
    proc = subprocess.run(
        cmd,
        cwd=str(tree),
        shell=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return {
        "command": cmd,
        "exit_code": proc.returncode,
        "stdout_tail": text[-800:],
    }


def untracked_paths(tree: Path) -> list[str]:
    proc = run_git(
        ["status", "--porcelain=v1", "--untracked-files=all"],
        tree,
    )
    die_git(proc, "git status")
    out: list[str] = []
    for line in (proc.stdout or "").splitlines():
        if line.startswith("?? "):
            out.append(line[3:].strip())
    return out


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    proc = run_git(["init", "--initial-branch=main"], root)
    if proc.returncode != 0:
        proc = run_git(["init"], root)
    die_git(proc, "git init")
    shutil.copy2(TEST_SRC, root / "test_payload.py")


def _commit(root: Path, message: str) -> str:
    proc = run_git(["add", "-A"], root)
    die_git(proc, "git add")
    proc = run_git(["commit", "-m", message], root)
    die_git(proc, "git commit")
    proc = run_git(["rev-parse", "HEAD"], root)
    die_git(proc, "git rev-parse")
    sha = (proc.stdout or "").strip()
    if len(sha) != 40:
        raise RuntimeError(f"unexpected sha {sha!r}")
    return sha


def _clone(src: Path, dest: Path) -> str:
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = run_git(["clone", "--", str(src), str(dest)], dest.parent)
    die_git(proc, "git clone")
    proc = run_git(["rev-parse", "HEAD"], dest)
    die_git(proc, "git rev-parse clone")
    return (proc.stdout or "").strip()


def scenario_untracked_required(tmp: Path) -> dict:
    """Developer has required_payload.txt untracked; clone at fix SHA does not."""
    src = tmp / "dev-untracked"
    clone = tmp / "clone-untracked"
    _init_repo(src)
    fix_sha = _commit(src, "fix: add payload test without committing payload")
    (src / MISSING_FILE).write_text(PAYLOAD_TEXT, encoding="utf-8")
    dev_run = run_test(src)
    clone_sha = _clone(src, clone)
    clone_run = run_test(clone)
    hand = tmp / "clone-untracked-hand"
    if hand.exists():
        shutil.rmtree(hand)
    shutil.copytree(clone, hand, dirs_exist_ok=True)
    shutil.copy2(src / MISSING_FILE, hand / MISSING_FILE)
    hand_run = run_test(hand)
    return {
        "scenario": "untracked-required-payload",
        "classification": "uncommitted-dependency",
        "missing_file": MISSING_FILE,
        "fix_sha": fix_sha,
        "clone_sha": clone_sha,
        "clone_sha_equals_fix_sha": clone_sha == fix_sha,
        "developer": dev_run,
        "clone": clone_run,
        "hand_copy": hand_run,
        "untracked_developer": untracked_paths(src),
        "untracked_clone": untracked_paths(clone),
        "developer_path": str(src),
        "clone_path": str(clone),
    }


def scenario_committed_control(tmp: Path) -> dict:
    """Same test, payload committed: both trees pass; clone SHA equals fix SHA."""
    src = tmp / "dev-committed"
    clone = tmp / "clone-committed"
    _init_repo(src)
    (src / MISSING_FILE).write_text(PAYLOAD_TEXT, encoding="utf-8")
    fix_sha = _commit(src, "fix: add payload test and required payload")
    dev_run = run_test(src)
    clone_sha = _clone(src, clone)
    clone_run = run_test(clone)
    return {
        "scenario": "committed-required-payload",
        "classification": "committed-control",
        "missing_file": None,
        "fix_sha": fix_sha,
        "clone_sha": clone_sha,
        "clone_sha_equals_fix_sha": clone_sha == fix_sha,
        "developer": dev_run,
        "clone": clone_run,
        "untracked_developer": untracked_paths(src),
        "untracked_clone": untracked_paths(clone),
        "developer_path": str(src),
        "clone_path": str(clone),
    }


def observe_product() -> dict:
    git_dir = REPO / ".git"
    cnf22 = REPO / "command-center" / "confirmation" / "CNF-0022-pre-fix-timetravel.json"
    is_git = git_dir.exists()
    note = (
        "Product worktree /opt/p2/ast-integrate has no .git object database, so it "
        "cannot be cloned at a product fix SHA. CNF-0022 (fix commit list) is also "
        "absent. Product-tree fixes are therefore NOT-CHECKED; the load-bearing "
        "clone/SHA experiment runs on an isolated fixture repository."
        if not is_git
        else "Product worktree is a git repository; see untracked inventory."
    )
    return {
        "path": str(REPO),
        "is_git": is_git,
        "cnf0022_present": cnf22.is_file() and cnf22.stat().st_size > 0,
        "note": note,
    }


def live_pair(tmp: Path) -> dict:
    missing = scenario_untracked_required(tmp)
    control = scenario_committed_control(tmp)
    cmd_dev = missing["developer"]["command"]
    cmd_clone = missing["clone"]["command"]
    cmd_cdev = control["developer"]["command"]
    cmd_cclone = control["clone"]["command"]
    identical = cmd_dev == cmd_clone == cmd_cdev == cmd_cclone
    return {
        "missing": missing,
        "control": control,
        "product": observe_product(),
        "command": cmd_dev,
        "identical_command_both_trees": identical,
        "ok": (
            missing["clone_sha_equals_fix_sha"]
            and control["clone_sha_equals_fix_sha"]
            and identical
            and missing["developer"]["exit_code"] == 0
            and missing["clone"]["exit_code"] != 0
            and missing["hand_copy"]["exit_code"] == 0
            and control["developer"]["exit_code"] == 0
            and control["clone"]["exit_code"] == 0
            and MISSING_FILE in missing["untracked_developer"]
            and MISSING_FILE not in missing["untracked_clone"]
        ),
    }
