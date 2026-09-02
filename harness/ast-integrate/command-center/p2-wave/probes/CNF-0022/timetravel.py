"""Disposable git-worktree time-travel. Git runs only under /tmp, never in the shared checkout."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from scenario import REPO, assert_isolated, build_all, git


def _color(rc: int) -> str:
    return "GREEN" if rc == 0 else "RED"


def pattern_of(parent_rc: int, fix_rc: int) -> str:
    return f"{_color(parent_rc)}-{_color(fix_rc)}"


def host_checkout_status() -> dict:
    git_dir = REPO / ".git"
    proc = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip() or f"rc={proc.returncode}"
    return {
        "path": str(REPO),
        "dot_git_present": git_dir.exists(),
        "git_rev_parse": tail[-400:],
        "is_git_repository": False if proc.returncode != 0 else git_dir.is_dir(),
        "product_fix_list_available": False,
    }


def run_test(worktree: Path, test_rel: str) -> dict:
    script = worktree / test_rel
    proc = subprocess.run(
        [sys.executable, "-B", str(script)],
        cwd=str(worktree),
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return {"exit_code": proc.returncode, "output": out}


def _digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _worktree_path(prefix: str) -> Path:
    return Path("/tmp") / f"{prefix}-{os.getpid()}-{uuid.uuid4().hex[:10]}"


def _remove_worktree(repo: Path, env: dict, wt: Path) -> bool:
    git(["worktree", "remove", "--force", str(wt)], repo, env, check=False)
    if wt.exists():
        shutil.rmtree(wt, ignore_errors=True)
    git(["worktree", "prune"], repo, env, check=False)
    return not wt.exists()


def examine_fix(built: dict) -> dict:
    repo = assert_isolated(Path(built["repo"]))
    env = built["env"]
    parent_sha = built["parent_sha"]
    fix_sha = built["fix_sha"]
    test_rel = built["test_rel"]
    index = repo / ".git" / "index"
    index_before = _digest(index)
    head_before = git(["rev-parse", "HEAD"], repo, env).stdout.strip()

    parent_wt = _worktree_path("cnf0022-parent")
    fix_wt = _worktree_path("cnf0022-fix")
    try:
        git(["worktree", "add", "--detach", str(parent_wt), parent_sha], repo, env)
        git(["worktree", "add", "--detach", str(fix_wt), fix_sha], repo, env)
        parent_run = run_test(parent_wt, test_rel)
        fix_run = run_test(fix_wt, test_rel)
        control = None
        if built.get("control_rel"):
            control = {
                "parent": run_test(parent_wt, built["control_rel"]),
                "fix": run_test(fix_wt, built["control_rel"]),
            }
    finally:
        parent_gone = _remove_worktree(repo, env, parent_wt)
        fix_gone = _remove_worktree(repo, env, fix_wt)

    index_after = _digest(index)
    head_after = git(["rev-parse", "HEAD"], repo, env).stdout.strip()
    pat = pattern_of(parent_run["exit_code"], fix_run["exit_code"])
    row = {
        "id": built["id"],
        "title": built["title"],
        "parent_sha": parent_sha,
        "fix_sha": fix_sha,
        "test_invocation": f"python3 -B {test_rel}",
        "parent_exit_code": parent_run["exit_code"],
        "fix_exit_code": fix_run["exit_code"],
        "parent_output": parent_run["output"],
        "fix_output": fix_run["output"],
        "pattern": pat,
        "classification": built["expected_classification"]
        if pat == built["expected_pattern"]
        else "repro-not-reproducible",
        "worktree_removed": parent_gone and fix_gone,
        "fixture_index_untouched": index_before == index_after,
        "fixture_head_untouched": head_before == head_after,
        "expected_pattern": built["expected_pattern"],
        "expected_classification": built["expected_classification"],
    }
    if control:
        cpat = pattern_of(control["parent"]["exit_code"], control["fix"]["exit_code"])
        row["control_test_invocation"] = f"python3 -B {built['control_rel']}"
        row["control_pattern"] = cpat
        row["control_parent_output"] = control["parent"]["output"]
        row["control_fix_output"] = control["fix"]["output"]
        row["control_expected_pattern"] = built.get("control_expected_pattern")
    return row


def prove_disposal(built: dict) -> dict:
    repo = assert_isolated(Path(built["repo"]))
    env = built["env"]
    wt = _worktree_path("cnf0022-disposal")
    index_before = _digest(repo / ".git" / "index")
    git(["worktree", "add", "--detach", str(wt), built["parent_sha"]], repo, env)
    listed = git(["worktree", "list", "--porcelain"], repo, env).stdout
    if str(wt) not in listed:
        raise RuntimeError("worktree add did not register")
    red = run_test(wt, built["test_rel"])
    gone = _remove_worktree(repo, env, wt)
    listed_after = git(["worktree", "list", "--porcelain"], repo, env).stdout
    still_listed = str(wt) in listed_after
    index_after = _digest(repo / ".git" / "index")
    missing_run = subprocess.run(
        [sys.executable, "-B", str(wt / built["test_rel"])],
        capture_output=True,
        text=True,
        timeout=15,
    )
    host_before = (REPO / ".git").exists()
    return {
        "path_gone": gone,
        "not_listed": not still_listed,
        "index_untouched": index_before == index_after,
        "removed_path_unrunnable": missing_run.returncode != 0,
        "parent_was_red": red["exit_code"] != 0,
        "host_git_created": (REPO / ".git").exists() and not host_before,
        "host_git_present_after": (REPO / ".git").exists(),
        "proof": (
            f"worktree {wt} added then removed; exists={wt.exists()} "
            f"listed_after={still_listed} index_same={index_before == index_after} "
            f"rerun_rc={missing_run.returncode}"
        ),
    }


def run_campaign() -> dict:
    host = host_checkout_status()
    base = Path(tempfile.mkdtemp(prefix="cnf0022-campaign-", dir="/tmp"))
    try:
        built = build_all(base)
        rows = [examine_fix(b) for b in built]
        disposal = prove_disposal(built[0])
        return {"host": host, "rows": rows, "disposal": disposal, "base": str(base)}
    finally:
        shutil.rmtree(base, ignore_errors=True)
