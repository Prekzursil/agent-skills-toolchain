#!/usr/bin/env python3
"""First-stage-boundary rollback rehearsal in a scratch git clone.

Does not run git add/commit/revert in the delivery worktree. Identity is passed
via process env and -c flags; global git config is not written.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

from estate import (  # noqa: E402
    S1_EVALUATOR_REL,
    apply_files,
    apply_stage,
    baseline_files,
    sha256_file,
)

RESTORE_COMMAND = "git -C \"$CLONE\" revert --no-edit HEAD"
S1_GONE = S1_EVALUATOR_REL


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "ARC-0063"
    env["GIT_AUTHOR_EMAIL"] = "arc0063@local"
    env["GIT_COMMITTER_NAME"] = "ARC-0063"
    env["GIT_COMMITTER_EMAIL"] = "arc0063@local"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git(clone: Path, *args: str) -> subprocess.CompletedProcess[str]:
    cmd = [
        "git",
        "-C",
        str(clone),
        "-c",
        "user.email=arc0063@local",
        "-c",
        "user.name=ARC-0063",
        *args,
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    )


def tree_sha(clone: Path) -> str:
    return git(clone, "rev-parse", "HEAD^{tree}").stdout.strip()


def rehearse_first_boundary(clone: Path | None = None) -> dict[str, Any]:
    own = clone is None
    tmp_ctx = tempfile.TemporaryDirectory(prefix="arc0063-scratch-") if own else None
    try:
        if clone is None:
            assert tmp_ctx is not None
            clone = Path(tmp_ctx.name) / "clone"
            clone.mkdir()
        subprocess.run(
            ["git", "init", "-b", "arc0063-hybrid", str(clone)],
            capture_output=True,
            text=True,
            check=True,
            env=_git_env(),
        )
        apply_files(clone, baseline_files())
        git(clone, "add", "-A")
        git(clone, "commit", "-m", "baseline: pre-hybrid fixture")
        baseline = tree_sha(clone)
        apply_stage(clone, "S1", None)
        git(clone, "add", "-A")
        git(clone, "commit", "-m", "PR S1: land permission evaluator")
        post_s1 = tree_sha(clone)
        if post_s1 == baseline:
            return {
                "pass": False,
                "reason": "s1-commit-did-not-change-tree",
                "scratch_clone": True,
            }
        if not (clone / S1_GONE).is_file():
            return {
                "pass": False,
                "reason": "s1-artifact-missing-before-revert",
                "scratch_clone": True,
            }
        git(clone, "revert", "--no-edit", "HEAD")
        post_revert = tree_sha(clone)
        gone = not (clone / S1_GONE).is_file()
        readme = (clone / "README.txt").is_file()
        equal = post_revert == baseline
        return {
            "pass": bool(equal and gone and readme),
            "stage_id": "S1",
            "scratch_clone": True,
            "baseline_tree_equals_post_revert": equal,
            "first_stage_artifact_removed": S1_GONE,
            "artifact_absent_after_revert": gone,
            "restore_command": RESTORE_COMMAND,
            "worktree_untouched": True,
            "baseline_tree": baseline,
            "post_s1_tree": post_s1,
            "post_revert_tree": post_revert,
        }
    except subprocess.CalledProcessError as exc:
        return {
            "pass": False,
            "reason": "git-failed",
            "cmd": exc.cmd,
            "stderr": (exc.stderr or "")[-1500:],
            "scratch_clone": True,
        }
    finally:
        if tmp_ctx is not None:
            tmp_ctx.cleanup()


def two_clone_rehearsal() -> dict[str, Any]:
    """Re-measure rollback with a second scratch clone (retry_policy field)."""
    a = rehearse_first_boundary()
    b = rehearse_first_boundary()
    agree = (
        a.get("baseline_tree_equals_post_revert")
        == b.get("baseline_tree_equals_post_revert")
        and a.get("pass") == b.get("pass")
        and a.get("artifact_absent_after_revert") == b.get("artifact_absent_after_revert")
    )
    out = dict(a)
    out["two_clone_readings_agree"] = agree
    out["second_clone_pass"] = b.get("pass")
    if not agree:
        out["pass"] = False
        out["reason"] = "two-clone-disagreement"
        out["reading_a"] = {
            "pass": a.get("pass"),
            "equal": a.get("baseline_tree_equals_post_revert"),
        }
        out["reading_b"] = {
            "pass": b.get("pass"),
            "equal": b.get("baseline_tree_equals_post_revert"),
        }
    elif not a.get("pass"):
        out["pass"] = False
    return out


def content_preservation_both_directions() -> dict[str, Any]:
    """Forward: S2 does not rewrite S1 evaluator. Reverse: S1 revert restores baseline."""
    with tempfile.TemporaryDirectory(prefix="arc0063-preserve-") as tmp:
        root = Path(tmp) / "estate"
        root.mkdir()
        apply_files(root, baseline_files())
        s1 = apply_stage(root, "S1", None)
        s1_eval = s1[S1_GONE]
        apply_stage(root, "S2", s1)
        forward = sha256_file(root / S1_GONE) == s1_eval
    rb = rehearse_first_boundary()
    reverse = bool(rb.get("baseline_tree_equals_post_revert") and rb.get("pass"))
    return {
        "pass": bool(forward and reverse),
        "forward_prior_bytes_unchanged": forward,
        "reverse_restores_pre_stage": reverse,
    }
