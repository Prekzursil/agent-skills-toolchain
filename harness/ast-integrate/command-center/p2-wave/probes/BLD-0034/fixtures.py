#!/usr/bin/env python3
"""Isolated git fixtures for BLD-0034 catalog controls.

All repos live under a caller-supplied directory (tempfile). Never mutates
/opt/p2/ast-integrate (no .git there; no add/commit/stash/checkout on it).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def init_repo(path: Path, *, first_commit_msg: str = "base") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    C.git(path, "init", "-b", "main")
    C.git(path, "config", "user.email", "bld0034@test.invalid")
    C.git(path, "config", "user.name", "BLD-0034")
    C.git(path, "config", "commit.gpgsign", "false")
    write(path / "README.md", "retained-base\n")
    C.git(path, "add", "README.md")
    C.git(path, "commit", "-m", first_commit_msg)
    return path


def store_identical_stash(repo: Path, message: str) -> str:
    """Stash-like merge commit whose trees equal HEAD. Existence is not unique work.

    git-stash requires a two-parent commit (HEAD + index). Both parents and the
    WIP tree are the retained HEAD tree so content comparison is empty.
    """
    tree = C.git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
    head = C.git(repo, "rev-parse", "HEAD").stdout.strip()
    index_commit = C.git(
        repo,
        "commit-tree",
        tree,
        "-p",
        head,
        "-m",
        f"index on main: {message}",
    ).stdout.strip()
    wip = C.git(
        repo,
        "commit-tree",
        tree,
        "-p",
        head,
        "-p",
        index_commit,
        "-m",
        f"WIP on main: {message}",
    ).stdout.strip()
    C.git(repo, "stash", "store", "-m", message, wip)
    return wip


def build(root: Path) -> dict:
    root = root.resolve()
    estate = init_repo(root / "estate")

    C.git(estate, "checkout", "-b", "squash-feature")
    write(estate / "extra.txt", "squash-unique-then-on-main\n")
    C.git(estate, "add", "extra.txt")
    C.git(estate, "commit", "-m", "feature extra")
    C.git(estate, "checkout", "main")
    C.git(estate, "merge", "--squash", "squash-feature")
    C.git(estate, "commit", "-m", "squash extra onto main")

    C.git(estate, "branch", "twin")
    C.git(estate, "tag", "v-identical")

    C.git(estate, "checkout", "-b", "unique-work")
    write(estate / "unique.txt", "only-on-unique-work\n")
    C.git(estate, "add", "unique.txt")
    C.git(estate, "commit", "-m", "unique work")
    C.git(estate, "checkout", "main")

    identical_stash_sha = store_identical_stash(estate, "identical-to-HEAD")

    write(estate / "u.txt", "untracked-only\n")
    push = C.git(
        estate,
        "stash",
        "push",
        "-m",
        "untracked-pathspec",
        "--",
        "u.txt",
        check=False,
    )
    combined = (push.stdout or "") + (push.stderr or "")
    stash_push_untracked = {
        "command": "git stash push -m untracked-pathspec -- u.txt",
        "returncode": push.returncode,
        "stdout": (push.stdout or "")[-500:],
        "stderr": (push.stderr or "")[-500:],
        "u_txt_still_on_disk": (estate / "u.txt").is_file(),
        "saved_nothing": push.returncode != 0
        or "No local changes to save" in combined
        or "pathspec" in combined.lower(),
    }

    wt_ours = root / "wt-ours"
    C.git(estate, "worktree", "add", str(wt_ours), "twin")

    foreign = init_repo(root / "foreign", first_commit_msg="foreign base")
    write(foreign / "FOREIGN.txt", "other-repository\n")
    C.git(foreign, "add", "FOREIGN.txt")
    C.git(foreign, "commit", "-m", "foreign unique")

    return {
        "root": str(root),
        "estate": str(estate),
        "wt_ours": str(wt_ours),
        "foreign": str(foreign),
        "identical_stash_sha": identical_stash_sha,
        "stash_push_untracked": stash_push_untracked,
        "retained": "main",
    }


def assert_controls(result: dict, estate: Path) -> None:
    """Raise SystemExit if any of the four catalog controls fail."""
    objs = result["objects"]

    def one(kind: str, name: str) -> dict:
        hits = [o for o in objs if o.get("kind") == kind and o.get("name") == name]
        if len(hits) != 1:
            raise SystemExit(f"control: expected 1 {kind}:{name} got {len(hits)}")
        return hits[0]

    twin = one("branch", "twin")
    if twin["verdict"] != C.SAFE or twin.get("empty_diff") is not True:
        raise SystemExit("control: twin must be SAFE-TO-RETIRE with empty diff")
    squash = one("branch", "squash-feature")
    anc = squash.get("ancestry") or {}
    if not anc.get("ahead") or squash.get("classified_unmerged") or squash["verdict"] != C.SAFE:
        raise SystemExit("control: squash-feature AHEAD must not be unmerged")
    unique = one("branch", "unique-work")
    if unique["verdict"] != C.RETAIN:
        raise SystemExit("control: unique-work must RETAIN")
    stashes = [o for o in objs if o.get("kind") == "stash"]
    if not any(s.get("verdict") == C.STASH_EMPTY and s.get("empty_diff") for s in stashes):
        raise SystemExit("control: stash existence is not unique work")
    attempt = one("stash-push-attempt", "untracked-pathspec")
    if attempt["verdict"] != C.STASH_SAVED_NOTHING:
        raise SystemExit("control: untracked pathspec stash must save nothing")
    foreign = [o for o in objs if o.get("verdict") == C.FOREIGN]
    if len(foreign) != 1:
        raise SystemExit("control: exactly one FOREIGN-WORKTREE")
    d1 = C.git(estate, "diff", "--exit-code", "main", "twin", check=False)
    d2 = C.git(estate, "diff", "--exit-code", "main", "squash-feature", check=False)
    if d1.returncode != 0 or d2.returncode != 0:
        raise SystemExit("control: two-dot diff not empty")
    if result.get("deletions_performed") is not False:
        raise SystemExit("control: deletions_performed must be false")


def classify_estate(meta: dict) -> dict:
    estate = Path(meta["estate"])
    extra = [Path(meta["foreign"])]
    result = C.enumerate_repo(
        estate,
        retained=meta["retained"],
        scope="control",
        extra_worktree_paths=extra,
    )
    result["stash_push_untracked"] = meta["stash_push_untracked"]
    saved = bool(meta["stash_push_untracked"]["saved_nothing"])
    result["objects"].append(
        {
            "kind": "stash-push-attempt",
            "name": "untracked-pathspec",
            "scope": "control",
            "verdict": C.STASH_SAVED_NOTHING if saved else C.UNPROVEN,
            "classified_unmerged": False,
            "empty_diff": False,
            "evidence": meta["stash_push_untracked"],
            "reason": (
                "git stash push -- <untracked path> did not save the file; "
                "stash existence is never unique-work proof."
            ),
        }
    )
    return result
