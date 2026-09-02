"""Build a disposable git history that plants a canary then deletes it from HEAD.

The live worktree is not a git repository. This fixture is the only history the
unit can honestly scan: commits, a second branch, and packed objects. The canary
body is never written under the program worktree.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

CANARY_REL = "secrets/planted.env"
CANARY_BRANCH = "canary-era"
PLACEHOLDER_REL = "config/placeholder.env"


class GitError(RuntimeError):
    pass


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "CNF-0108-fixture",
            "GIT_AUTHOR_EMAIL": "cnf-0108@invalid.example",
            "GIT_COMMITTER_NAME": "CNF-0108-fixture",
            "GIT_COMMITTER_EMAIL": "cnf-0108@invalid.example",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
        }
    )
    p = subprocess.run(
        ["git", "-C", str(repo), *args],
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and p.returncode != 0:
        tail = ((p.stdout or "") + (p.stderr or "")).strip()[-1500:]
        raise GitError(f"git {' '.join(args)} rc={p.returncode} {tail}")
    return p


def build_history_repo(root: Path, prefix: str, body: str) -> dict:
    """Create commits/refs/pack so a working-tree scan at HEAD misses the canary."""
    root = Path(root)
    if root.exists():
        raise GitError(f"fixture root already exists: {root}")
    root.mkdir(parents=True)
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "CNF-0108-fixture")
    git(root, "config", "user.email", "cnf-0108@invalid.example")
    git(root, "config", "commit.gpgsign", "false")
    git(root, "config", "core.autocrlf", "false")

    (root / "README.md").write_text(
        "CNF-0108 fixture repository. Placeholder only.\n", encoding="utf-8"
    )
    (root / "config").mkdir()
    (root / PLACEHOLDER_REL).write_text(
        "API_KEY=placeholder\nTOKEN=changeme\n", encoding="utf-8"
    )
    git(root, "add", "README.md", PLACEHOLDER_REL)
    git(root, "commit", "-m", "c1: baseline without canary")
    c1 = git(root, "rev-parse", "HEAD").stdout.strip()

    secrets_dir = root / "secrets"
    secrets_dir.mkdir()
    planted = secrets_dir / "planted.env"
    # Synthetic canary: recognisable non-secret prefix plus random body.
    planted.write_text(
        f"# synthetic planted canary — not a live credential\n"
        f"CNF0108_PLANTED={prefix}{body}\n",
        encoding="utf-8",
    )
    git(root, "add", CANARY_REL)
    git(root, "commit", "-m", "c2: plant synthetic canary")
    c2 = git(root, "rev-parse", "HEAD").stdout.strip()
    blob = git(root, "rev-parse", f"HEAD:{CANARY_REL}").stdout.strip()
    git(root, "branch", CANARY_BRANCH, c2)

    planted.unlink()
    git(root, "rm", CANARY_REL)
    git(root, "commit", "-m", "c3: delete canary from working tree")
    c3 = git(root, "rev-parse", "HEAD").stdout.strip()

    git(root, "repack", "-Ad")
    git(root, "prune-packed")
    packs = sorted(p.name for p in (root / ".git" / "objects" / "pack").glob("*.pack"))
    if not packs:
        raise GitError("repack produced no pack files")

    wt_has = (root / CANARY_REL).is_file()
    refs = git(root, "show-ref", "--heads").stdout.strip().splitlines()
    return {
        "repo": str(root),
        "commits": {"c1": c1, "c2_canary": c2, "c3_head": c3},
        "canary_commit": c2,
        "head_commit": c3,
        "canary_blob": blob,
        "canary_path": CANARY_REL,
        "canary_branch": CANARY_BRANCH,
        "refs": refs,
        "packs": packs,
        "head_working_tree_has_canary_file": wt_has,
        "placeholder_path": PLACEHOLDER_REL,
    }
