#!/usr/bin/env python3
"""Two-surface abandoned-work salvage classifier for WFA-0022.

Surface A: git object recovery (cat-file / log / reflog). Read-only.
Surface B: byte-level search of surviving live trees for the same content.

CONTENT-LOST is proven only when BOTH surfaces were actually queried and
both missed. A changelog mention of a path is not preservation.
This module never deletes, prunes, or garbage-collects.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "WFA-0022"
SENTINEL = "SUCCESS:WFA-0022"
OUT_REL = "command-center/wfa/WFA-0022-sweep-abandoned-salvage.json"
SCHEMA_REL = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/SweepReport"

PRESERVED = "CONTENT-PRESERVED-ELSEWHERE"
LOST = "CONTENT-LOST"
UNPROVEN = "UNPROVEN-LOST"

GIT_READ = frozenset(
    {
        "cat-file",
        "show",
        "log",
        "diff",
        "ls-tree",
        "rev-parse",
        "reflog",
        "rev-list",
        "status",
        "hash-object",
        "ls-files",
        "branch",
        "for-each-ref",
        "worktree",
    }
)
SKIP_DIR = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".mypy_cache",
        ".pytest_cache",
        ".tox",
        "captures",
    }
)
MAX_INDEX_BYTES = 2_000_000


class GitWriteRefused(RuntimeError):
    pass


def lf(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_lf(raw: bytes) -> str:
    return hashlib.sha256(lf(raw)).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = lf(path.read_bytes())
    return hashlib.sha256(raw).hexdigest(), len(raw)


def git_ro(repo: Path, *args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    """Read-only git. Refuses writes, gc, prune, and hash-object -w."""
    if not args:
        raise GitWriteRefused("empty git argv")
    cmd = args[0]
    if cmd not in GIT_READ:
        raise GitWriteRefused(f"refused git write/mutation: {cmd}")
    if cmd == "hash-object" and "-w" in args:
        raise GitWriteRefused("refused git hash-object -w")
    if cmd == "worktree" and (len(args) < 2 or args[1] != "list"):
        raise GitWriteRefused(f"refused git worktree {args[1:]}")
    env = os.environ.copy()
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        check=False,
    )


def git_present(repo: Path) -> bool:
    git_dir = repo / ".git"
    if git_dir.is_dir() or git_dir.is_file():
        return True
    try:
        p = git_ro(repo, "rev-parse", "--is-inside-work-tree")
    except (GitWriteRefused, OSError, subprocess.TimeoutExpired):
        return False
    return p.returncode == 0 and (p.stdout or "").strip() == "true"


@dataclass
class GitRecovery:
    ok: bool
    surface_available: bool
    blob_id: str | None = None
    ref: str | None = None
    sha256: str | None = None
    bytes: int = 0
    reason: str = ""
    content: bytes | None = field(default=None, repr=False)


def _rev_parse(repo: Path, spec: str) -> str | None:
    p = git_ro(repo, "rev-parse", "--verify", "--quiet", spec)
    if p.returncode != 0:
        return None
    val = (p.stdout or "").strip()
    return val or None


def git_ro_bytes(repo: Path, *args: str, timeout: int = 30) -> subprocess.CompletedProcess[bytes]:
    if not args or args[0] not in GIT_READ:
        raise GitWriteRefused(f"refused git write/mutation: {args[:1]}")
    if args[0] == "hash-object" and "-w" in args:
        raise GitWriteRefused("refused git hash-object -w")
    env = os.environ.copy()
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        timeout=timeout,
        env=env,
        check=False,
    )


def _cat_blob(repo: Path, blob_id: str) -> bytes | None:
    p = git_ro_bytes(repo, "cat-file", "-p", blob_id)
    if p.returncode != 0:
        return None
    return p.stdout


def _reflog_hit(repo: Path, commit: str) -> str | None:
    p = git_ro(repo, "reflog", "--all")
    if p.returncode != 0:
        return None
    short = commit[:12]
    for line in (p.stdout or "").splitlines():
        if commit in line or short in line:
            return line.strip()
    return None


def recover_path(repo: Path, relpath: str) -> GitRecovery:
    """Recover bytes for relpath from git objects. Never fabricates a miss."""
    relpath = relpath.replace("\\", "/").lstrip("/")
    if not git_present(repo):
        return GitRecovery(
            ok=False,
            surface_available=False,
            reason="GIT-OBJECT-STORE-ABSENT",
        )
    specs = [f"HEAD:{relpath}"]
    log = git_ro(
        repo,
        "log",
        "--all",
        "--full-history",
        "-n",
        "1",
        "--pretty=%H",
        "--",
        relpath,
    )
    commit = (log.stdout or "").strip() if log.returncode == 0 else ""
    if commit:
        specs.append(f"{commit}:{relpath}")
    deleting = git_ro(
        repo,
        "log",
        "--all",
        "--diff-filter=D",
        "-n",
        "1",
        "--pretty=%H",
        "--",
        relpath,
    )
    deleted_at = (deleting.stdout or "").strip() if deleting.returncode == 0 else ""
    if deleted_at:
        # ~1, never caret: PowerShell mangles <rev>^{commit} on the Windows box.
        specs.append(f"{deleted_at}~1:{relpath}")
    seen: set[str] = set()
    for spec in specs:
        if spec in seen:
            continue
        seen.add(spec)
        blob = _rev_parse(repo, spec)
        if not blob:
            continue
        raw = _cat_blob(repo, blob)
        if raw is None:
            continue
        norm = lf(raw)
        ref_name = spec
        if commit:
            hit = _reflog_hit(repo, commit)
            if hit:
                ref_name = f"{spec} reflog:{hit}"
        return GitRecovery(
            ok=True,
            surface_available=True,
            blob_id=blob,
            ref=ref_name,
            sha256=hashlib.sha256(norm).hexdigest(),
            bytes=len(norm),
            content=norm,
        )
    return GitRecovery(
        ok=False,
        surface_available=True,
        reason="GIT-LOOKUP-MISS",
    )


def live_search(
    roots: Iterable[Path],
    want_sha256: str,
    *,
    max_bytes: int = MAX_INDEX_BYTES,
) -> list[dict[str, Any]]:
    """Byte-level search. Path-string mentions never match."""
    hits: list[dict[str, Any]] = []
    want = want_sha256.lower()
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        if root.is_file():
            candidates = [root]
        else:
            candidates = [p for p in root.rglob("*") if p.is_file()]
        for path in candidates:
            if any(part in SKIP_DIR for part in path.parts):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > max_bytes:
                continue
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            sha, n = sha256_lf(raw), len(lf(raw))
            if sha == want:
                hits.append(
                    {
                        "path": path.as_posix(),
                        "sha256": sha,
                        "bytes": n,
                    }
                )
    return hits


def path_mentions(files: Iterable[Path], needle: str) -> list[str]:
    """Locations that NAME a path. Not a preservation proof."""
    found: list[str] = []
    for path in files:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if needle in text:
            found.append(path.as_posix())
    return found


def classify(git: GitRecovery, live_hits: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """LOST only when both surfaces ran and both missed."""
    if live_hits:
        loc = str(live_hits[0]["path"])
        return {
            "classification": PRESERVED,
            "preserving_location": loc,
            "why": "surface-B-byte-match",
            "live_hit_count": len(live_hits),
        }
    if git.ok and git.blob_id:
        loc = f"git:blob={git.blob_id} ref={git.ref}"
        return {
            "classification": PRESERVED,
            "preserving_location": loc,
            "why": "surface-A-git-object",
            "live_hit_count": 0,
        }
    if git.surface_available:
        return {
            "classification": LOST,
            "preserving_location": None,
            "why": "both-surfaces-miss",
            "live_hit_count": 0,
        }
    return {
        "classification": UNPROVEN,
        "preserving_location": None,
        "why": "git-surface-unavailable-cannot-prove-lost",
        "live_hit_count": 0,
    }


def git_recovery_public(git: GitRecovery) -> dict[str, Any]:
    return {
        "ok": git.ok,
        "surface_available": git.surface_available,
        "blob_id": git.blob_id,
        "ref": git.ref,
        "sha256": git.sha256,
        "bytes": git.bytes,
        "reason": git.reason,
    }


def judge(
    *,
    item_id: str,
    kind: str,
    path: str,
    git: GitRecovery,
    live_hits: Sequence[dict[str, Any]],
    mentions: Sequence[str] | None = None,
    salvage_worthy: bool = False,
    does: str = "",
) -> dict[str, Any]:
    verdict = classify(git, live_hits)
    row: dict[str, Any] = {
        "id": item_id,
        "kind": kind,
        "path": path,
        "git_recovery": git_recovery_public(git),
        "live_search": {
            "hits": list(live_hits),
            "mentions_are_not_preservation": True,
            "mention_locations": list(mentions or []),
        },
        "classification": verdict["classification"],
        "preserving_location": verdict["preserving_location"],
        "why": verdict["why"],
        "salvage_worthy": bool(salvage_worthy)
        and verdict["classification"] == PRESERVED,
        "does": does,
    }
    if row["salvage_worthy"]:
        row["candidate"] = {
            "id": f"wfa-0022-{item_id}",
            "name": Path(path).name,
            "does": does,
            "provenance": {
                "path": verdict["preserving_location"],
                "git_blob": git.blob_id,
                "git_ref": git.ref,
                "sha256": git.sha256
                or (live_hits[0]["sha256"] if live_hits else None),
                "recovery": verdict["why"],
            },
        }
    else:
        row["candidate"] = None
    return row
