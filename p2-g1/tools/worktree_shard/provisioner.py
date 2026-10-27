"""Worktree-per-shard provisioning with content-preserving teardown (IMP-0446).

Teardown authorization is NEVER derived from commit ancestry: a squash-merged
branch reports AHEAD even though every byte is preserved on main. The only
authorization inputs are a MERGED pull-request state or a byte-level
content-digest proof that every file in the worktree exists somewhere under
the caller-supplied preserve roots.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

UNPROVEN_TEARDOWN = "UNPROVEN_TEARDOWN"
FIXTURE_MARKER = ".imp0446-fixture"


def git(cwd: Path | str, *args: Any, check: bool = True) -> str:
    """Run git in *cwd* and return stripped stdout."""
    proc = subprocess.run(
        ["git", "-C", str(cwd), *[str(a) for a in args]],
        capture_output=True,
        text=True,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(str(a) for a in args)} rc={proc.returncode}: "
            f"{(proc.stderr or proc.stdout).strip()}"
        )
    return (proc.stdout or "").strip()


def _commit(cwd: Path | str, message: str) -> str:
    git(cwd, "commit", "-m", message)
    return git(cwd, "rev-parse", "HEAD")


def init_fixture_repo(path: Path | str) -> Path:
    """Create a throwaway git repo on branch main with one base commit."""
    repo = Path(path)
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init")
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    git(repo, "config", "user.email", "fixture@imp0446.local")
    git(repo, "config", "user.name", "IMP-0446 Fixture")
    git(repo, "config", "commit.gpgsign", "false")
    (repo / FIXTURE_MARKER).write_text("fixture repo for IMP-0446 probes\n", encoding="utf-8")
    (repo / "base.txt").write_text("base content shared by every branch\n", encoding="utf-8")
    git(repo, "add", FIXTURE_MARKER, "base.txt")
    _commit(repo, "base: initial fixture commit")
    return repo


@dataclass
class Shard:
    """A provisioned disposable worktree with its own git index."""

    shard_id: str
    path: Path
    branch: str
    repo: Path
    index_path: Path

    def as_dict(self) -> dict[str, Any]:
        return {
            "shard_id": self.shard_id,
            "path": str(self.path),
            "branch": self.branch,
            "repo": str(self.repo),
            "index_path": str(self.index_path),
        }


def provision_shard(
    repo: Path | str, shard_id: str, parent_dir: Path | str | None = None
) -> Shard:
    """Provision one disposable worktree (own branch, own index) per shard."""
    repo = Path(repo)
    parent = Path(parent_dir) if parent_dir is not None else repo.parent / "shards"
    parent.mkdir(parents=True, exist_ok=True)
    path = parent / shard_id
    branch = f"shard/{shard_id}"
    git(repo, "worktree", "add", "-b", branch, str(path))
    git_dir = Path(git(path, "rev-parse", "--absolute-git-dir"))
    return Shard(shard_id=shard_id, path=path, branch=branch, repo=repo, index_path=git_dir / "index")


def staged_names(worktree: Path | str) -> list[str]:
    """Names staged in *worktree*'s own index (isolation witness)."""
    out = git(worktree, "diff", "--cached", "--name-only")
    return [line for line in out.splitlines() if line]


@dataclass
class Ancestry:
    """Recorded beside every decision; never an authorization input."""

    head: str
    main_ref: str
    ahead: int
    behind: int
    is_ancestor: bool
    dirty: bool

    @property
    def reports_ahead(self) -> bool:
        return self.ahead > 0

    @property
    def would_authorize_delete(self) -> bool:
        return naive_ancestry_authorize(self)

    def as_dict(self) -> dict[str, Any]:
        return {
            "head": self.head,
            "main_ref": self.main_ref,
            "ahead": self.ahead,
            "behind": self.behind,
            "is_ancestor": self.is_ancestor,
            "dirty": self.dirty,
            "reports_ahead": self.reports_ahead,
            "would_authorize_delete": self.would_authorize_delete,
        }


def compute_ancestry(worktree: Path | str, main_ref: str) -> Ancestry:
    head = git(worktree, "rev-parse", "HEAD")
    ahead = int(git(worktree, "rev-list", "--count", f"{main_ref}..HEAD"))
    behind = int(git(worktree, "rev-list", "--count", f"HEAD..{main_ref}"))
    rc = subprocess.run(
        ["git", "-C", str(worktree), "merge-base", "--is-ancestor", "HEAD", main_ref],
        capture_output=True,
    ).returncode
    dirty = bool(git(worktree, "status", "--porcelain"))
    return Ancestry(
        head=head,
        main_ref=main_ref,
        ahead=ahead,
        behind=behind,
        is_ancestor=rc == 0,
        dirty=dirty,
    )


def naive_ancestry_authorize(ancestry: Ancestry) -> bool:
    """The DANGEROUS route: 'HEAD is contained in main, safe to delete'.

    Squash-merge makes this refuse a fully-preserved branch, and — worse —
    it authorizes deleting a DIRTY tree sitting on main. Kept only so probes
    can prove production disagrees with it.
    """
    return ancestry.is_ancestor and not ancestry.reports_ahead


@dataclass
class Proof:
    kind: str
    ok: bool
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "ok": self.ok, "detail": self.detail}


def _iter_files(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        return
    for p in sorted(root.rglob("*")):
        if p.is_file() and ".git" not in p.relative_to(root).parts:
            yield p


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_digest_proof(worktree: Path | str, preserve_roots: Iterable[Path | str]) -> Proof:
    """Every byte in the worktree must exist somewhere under a preserve root."""
    worktree = Path(worktree)
    preserved: set[str] = set()
    roots = [Path(r) for r in preserve_roots]
    for root in roots:
        for f in _iter_files(root):
            preserved.add(_sha256(f))
    missing: list[str] = []
    checked = 0
    for f in _iter_files(worktree):
        checked += 1
        if _sha256(f) not in preserved:
            missing.append(str(f.relative_to(worktree)))
    return Proof(
        kind="content-digest",
        ok=checked > 0 and not missing,
        detail={
            "checked": checked,
            "missing": missing[:20],
            "preserve_roots": [str(r) for r in roots],
        },
    )


def merged_pr_proof(pr_state: Mapping[str, Any] | None) -> Proof:
    """Only a structurally MERGED PR authorizes; ancestry-shaped fields do not."""
    state = dict(pr_state or {})
    ok = state.get("merged") is True and str(state.get("state", "")).upper() == "MERGED"
    return Proof(kind="merged-pr", ok=ok, detail=state)


def authorize_teardown(proofs: Iterable[Proof]) -> bool:
    """Authorization = any positive proof; ancestry is not a proof kind."""
    return any(p.ok for p in proofs)


@dataclass
class TeardownDecision:
    shard_id: str
    authorized: bool
    refused_reason: str | None
    executed: bool
    worktree_still_present: bool
    ancestry: Ancestry
    proofs: list[Proof]
    side_by_side: dict[str, Any]
    ancestry_used_as_authorization: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "shard_id": self.shard_id,
            "authorized": self.authorized,
            "refused_reason": self.refused_reason,
            "executed": self.executed,
            "worktree_still_present": self.worktree_still_present,
            "ancestry": self.ancestry.as_dict(),
            "proofs": [p.as_dict() for p in self.proofs],
            "side_by_side": self.side_by_side,
            "ancestry_used_as_authorization": self.ancestry_used_as_authorization,
        }


def _remove_worktree(repo: Path, worktree: Path) -> None:
    try:
        git(repo, "worktree", "remove", "--force", str(worktree))
    except RuntimeError:
        shutil.rmtree(worktree, ignore_errors=True)
        git(repo, "worktree", "prune", check=False)


def teardown_shard(
    *,
    worktree: Path | str,
    repo: Path | str,
    shard_id: str,
    main_ref: str,
    preserve_roots: Iterable[Path | str],
    pr_state: Mapping[str, Any] | None = None,
    execute: bool = False,
) -> TeardownDecision:
    """Refuse to delete until the shard's content is proven preserved elsewhere."""
    worktree = Path(worktree)
    repo = Path(repo)
    ancestry = compute_ancestry(worktree, main_ref)
    proofs = [
        content_digest_proof(worktree, preserve_roots),
        merged_pr_proof(pr_state),
    ]
    authorized = authorize_teardown(proofs)
    naive = naive_ancestry_authorize(ancestry)
    side_by_side = {
        "ancestry_authorize": naive,
        "content_authorize": proofs[0].ok,
        "merged_pr_authorize": proofs[1].ok,
        "production_authorized": authorized,
        "routes_disagree": naive != authorized,
    }
    executed = False
    if authorized and execute:
        _remove_worktree(repo, worktree)
        executed = True
    return TeardownDecision(
        shard_id=shard_id,
        authorized=authorized,
        refused_reason=None if authorized else UNPROVEN_TEARDOWN,
        executed=executed,
        worktree_still_present=worktree.exists(),
        ancestry=ancestry,
        proofs=proofs,
        side_by_side=side_by_side,
    )


# ---------------------------------------------------------------------------
# Probe fixtures (throwaway repos inside the caller's TemporaryDirectory).
# ---------------------------------------------------------------------------

_TRACKED_PAYLOAD = "feature payload preserved verbatim by the squash merge\n"


def build_squash_merge_fixture(dest: Path | str) -> dict[str, Any]:
    """Content SAFE / ancestry UNSAFE: fully squash-merged branch reports AHEAD."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    repo = init_fixture_repo(dest / "repo")
    wt = dest / "feature-wt"
    git(repo, "worktree", "add", "-b", "feature", str(wt), "main")
    (wt / "tracked.txt").write_text(_TRACKED_PAYLOAD, encoding="utf-8")
    git(wt, "add", "tracked.txt")
    _commit(wt, "feat: tracked payload")
    # Squash-merge simulation: identical bytes land on main in a NEW commit,
    # so the feature commit is not an ancestor of main.
    (repo / "tracked.txt").write_text(_TRACKED_PAYLOAD, encoding="utf-8")
    git(repo, "add", "tracked.txt")
    _commit(repo, "squash: feature payload onto main")
    return {
        "repo": repo,
        "worktree": wt,
        "main_ref": "main",
        "preserve_roots": [repo],
    }


def build_unproven_fixture(dest: Path | str) -> dict[str, Any]:
    """Dirty tree on main with unique bytes: ancestry says EQUAL, content says NO."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    repo = init_fixture_repo(dest / "repo")
    wt = dest / "unproven-wt"
    git(repo, "worktree", "add", "-b", "unproven", str(wt), "main")
    unique_rel = "notes/unique-canary.txt"
    unique_bytes = f"unproven-unique-{uuid.uuid4().hex}\n".encode("utf-8")
    unique_path = wt / unique_rel
    unique_path.parent.mkdir(parents=True, exist_ok=True)
    unique_path.write_bytes(unique_bytes)
    return {
        "repo": repo,
        "worktree": wt,
        "main_ref": "main",
        "preserve_roots": [repo],
        "unique_path": unique_path,
        "unique_bytes": unique_bytes,
        "unique_rel": unique_rel,
    }


def harvest_unique_into(store: Path | str, source: Path | str, unique_rel: str) -> Path:
    """Preserve *source* bytes under *store*/*unique_rel* (the good twin)."""
    target = Path(store) / unique_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(Path(source).read_bytes())
    return target


def build_pr_merged_unique_fixture(dest: Path | str) -> dict[str, Any]:
    """Committed unique bytes + structured MERGED pr_state: PR route authorizes."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    repo = init_fixture_repo(dest / "repo")
    wt = dest / "pr-wt"
    git(repo, "worktree", "add", "-b", "pr-feature", str(wt), "main")
    (wt / "pr-unique.txt").write_bytes(f"pr-unique-{uuid.uuid4().hex}\n".encode("utf-8"))
    git(wt, "add", "pr-unique.txt")
    _commit(wt, "feat: unique bytes merged via PR")
    pr_state = {
        "state": "MERGED",
        "merged": True,
        "number": 446,
        "ahead": 1,
        "commits_ahead": 1,
        "is_ancestor": False,
    }
    return {
        "repo": repo,
        "worktree": wt,
        "main_ref": "main",
        "preserve_roots": [repo],
        "pr_state": pr_state,
    }


__all__ = [
    "UNPROVEN_TEARDOWN",
    "FIXTURE_MARKER",
    "Ancestry",
    "Proof",
    "Shard",
    "TeardownDecision",
    "authorize_teardown",
    "build_pr_merged_unique_fixture",
    "build_squash_merge_fixture",
    "build_unproven_fixture",
    "compute_ancestry",
    "content_digest_proof",
    "git",
    "harvest_unique_into",
    "init_fixture_repo",
    "merged_pr_proof",
    "naive_ancestry_authorize",
    "provision_shard",
    "staged_names",
    "teardown_shard",
]
